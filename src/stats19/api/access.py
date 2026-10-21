"""Cloudflare Access JWT check at the origin (PLAN-006 C3).

Remote requests reach the API through Cloudflare Access and the tunnel. Caddy's tunnel site
marks them with ``X-Stats19-Edge: tunnel`` (the LAN site strips the header, so it can't be
forged from the LAN). A marked request must carry a valid ``Cf-Access-Jwt-Assertion``:
RS256, signed by one of the team's keys, for this application (``aud``) and team (``iss``),
not expired. Otherwise: 401. So a mistake in the Access settings can't open the API.

Unmarked requests (the LAN site, Docker-internal calls such as the PDF renderer) aren't
checked. Marked requests with Access not configured are refused: fail closed.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

import httpx
import jwt
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)

EDGE_HEADER = "X-Stats19-Edge"
JWT_HEADER = "Cf-Access-Jwt-Assertion"
MIN_REFETCH_S = 30.0  # an unknown key id refetches the keys, at most this often
LEEWAY_S = 30  # clock skew between Cloudflare and the host

Fetch = Callable[[str], dict]


class AccessDenied(Exception):
    pass


def _fetch(url: str) -> dict:
    r = httpx.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


class AccessVerifier:
    """Verifies Access JWTs against the team's published keys (cached)."""

    def __init__(
        self,
        issuer: str,
        audience: str,
        fetch: Fetch = _fetch,
        min_refetch_s: float = MIN_REFETCH_S,
    ):
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self._fetch = fetch
        self._min_refetch_s = min_refetch_s
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at = 0.0
        self._lock = threading.Lock()

    @classmethod
    def from_settings(cls, team_domain: str | None, audience: str | None) -> AccessVerifier | None:
        if not team_domain or not audience:
            return None
        domain = team_domain.removeprefix("https://").rstrip("/")
        return cls(f"https://{domain}", audience)

    @property
    def certs_url(self) -> str:
        return f"{self.issuer}/cdn-cgi/access/certs"

    def _key(self, kid: str) -> jwt.PyJWK:
        with self._lock:
            # Cloudflare rotates its keys: an unknown kid refetches them, rate-limited so
            # forged tokens can't make the API hammer Cloudflare
            due = time.monotonic() - self._fetched_at >= self._min_refetch_s
            if kid not in self._keys and (not self._keys or due):
                keys = jwt.PyJWKSet.from_dict(self._fetch(self.certs_url)).keys
                self._keys = {k.key_id: k for k in keys if k.key_id}
                self._fetched_at = time.monotonic()
            key = self._keys.get(kid)
        if key is None:
            raise AccessDenied("unknown signing key")
        return key

    def verify(self, token: str) -> dict:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256":
                raise AccessDenied("unexpected algorithm")
            key = self._key(header.get("kid", ""))
            return jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                leeway=LEEWAY_S,
                options={"require": ["exp", "iat", "aud", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise AccessDenied(str(exc)) from exc


def _unauthorised(request: Request, message: str) -> JSONResponse:
    error = {"code": "unauthorised", "message": message}
    ref = getattr(request.state, "ref", None)  # set by stats19.api.request_log
    if ref is not None:
        error["ref"] = ref
    return JSONResponse(status_code=401, content={"success": False, "data": None, "error": error})


def install_access_check(app: FastAPI, verifier: AccessVerifier | None) -> None:
    """Require a valid Access JWT on every request that came through the tunnel."""
    app.state.access = verifier  # None means tunnel requests are all refused

    @app.middleware("http")
    async def _access(request: Request, call_next):
        if request.headers.get(EDGE_HEADER) != "tunnel":
            return await call_next(request)
        if verifier is None:
            log.error("tunnel request refused: Cloudflare Access isn't configured")
            return _unauthorised(request, "Remote access isn't configured.")
        token = request.headers.get(JWT_HEADER)
        if not token:
            return _unauthorised(request, "Sign in through Cloudflare Access.")
        try:
            claims = verifier.verify(token)
        except AccessDenied as exc:
            log.warning("tunnel request refused: %s", exc)
            return _unauthorised(request, "Your sign-in couldn't be verified. Reload the page.")
        request.state.access_email = claims.get("email")
        return await call_next(request)
