"""Cloudflare Access JWT check at the origin (PLAN-006 C3).

Requests that came through the tunnel carry X-Stats19-Edge: tunnel (set by Caddy's tunnel
site, stripped by the LAN site). They must also carry a valid Access JWT, or get 401.
"""

import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from stats19.api.access import EDGE_HEADER, JWT_HEADER, AccessVerifier, install_access_check

TEAM = "https://team.cloudflareaccess.com"
AUD = "aud-tag-123"


def _key(kid: str):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    return private, public_jwk | {"kid": kid, "alg": "RS256", "use": "sig"}


PRIVATE, PUBLIC_JWK = _key("k1")
OTHER_PRIVATE, _ = _key("k1")  # same kid, different key: a forged token


def token(private=PRIVATE, kid="k1", **claims) -> str:
    now = int(time.time())
    body = {"aud": [AUD], "iss": TEAM, "iat": now, "exp": now + 600, "email": "me@example.com"}
    return jwt.encode(body | claims, private, algorithm="RS256", headers={"kid": kid})


class Fetcher:
    def __init__(self, keys: list[dict]):
        self.keys, self.calls = keys, 0

    def __call__(self, url: str) -> dict:
        self.calls += 1
        assert url == f"{TEAM}/cdn-cgi/access/certs"
        return {"keys": self.keys}


def client(verifier: AccessVerifier | None) -> TestClient:
    app = FastAPI()
    install_access_check(app, verifier)

    @app.get("/api/meta")
    def meta() -> dict:
        return {"success": True}

    return TestClient(app)


@pytest.fixture
def verifier():
    return AccessVerifier(TEAM, AUD, fetch=Fetcher([PUBLIC_JWK]))


def tunnel(jwt_value: str | None = None) -> dict:
    headers = {EDGE_HEADER: "tunnel"}
    if jwt_value is not None:
        headers[JWT_HEADER] = jwt_value
    return headers


def test_a_valid_access_token_through_the_tunnel_passes(verifier):
    r = client(verifier).get("/api/meta", headers=tunnel(token()))

    assert r.status_code == 200


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(lambda: token(exp=int(time.time()) - 60), id="expired"),
        pytest.param(lambda: token(aud=["someone-else"]), id="wrong-aud"),
        pytest.param(lambda: token(iss="https://evil.cloudflareaccess.com"), id="wrong-iss"),
        pytest.param(lambda: token(private=OTHER_PRIVATE), id="wrong-key"),
        pytest.param(lambda: jwt.encode({"aud": [AUD], "iss": TEAM}, "x", "HS256"), id="hs256"),
        pytest.param(lambda: "not-a-jwt", id="garbage"),
    ],
)
def test_bad_tokens_through_the_tunnel_are_refused(verifier, bad):
    r = client(verifier).get("/api/meta", headers=tunnel(bad()))

    assert r.status_code == 401
    assert r.json()["success"] is False
    assert r.json()["error"]["code"] == "unauthorised"


def test_the_tunnel_without_a_token_is_refused(verifier):
    assert client(verifier).get("/api/meta", headers=tunnel()).status_code == 401


def test_lan_requests_are_not_checked(verifier):
    # no edge header: the LAN site (which strips it) or Docker-internal calls (PDF renderer)
    assert client(verifier).get("/api/meta").status_code == 200


def test_the_tunnel_fails_closed_when_access_is_not_configured():
    c = client(None)

    assert c.get("/api/meta", headers=tunnel(token())).status_code == 401
    assert c.get("/api/meta").status_code == 200  # the LAN still works


def test_keys_are_cached_and_refetched_for_an_unknown_kid():
    new_private, new_jwk = _key("k2")
    fetch = Fetcher([PUBLIC_JWK])
    v = AccessVerifier(TEAM, AUD, fetch=fetch, min_refetch_s=0)
    c = client(v)

    assert c.get("/api/meta", headers=tunnel(token())).status_code == 200
    assert c.get("/api/meta", headers=tunnel(token())).status_code == 200
    assert fetch.calls == 1  # cached

    fetch.keys = [PUBLIC_JWK, new_jwk]  # Cloudflare rotated its keys
    assert c.get("/api/meta", headers=tunnel(token(new_private, kid="k2"))).status_code == 200
    assert fetch.calls == 2


def test_from_settings_needs_both_values():
    assert AccessVerifier.from_settings(None, AUD) is None
    assert AccessVerifier.from_settings("team.cloudflareaccess.com", None) is None
    v = AccessVerifier.from_settings("team.cloudflareaccess.com", AUD)
    assert v is not None and v.issuer == TEAM
