"""One log line per API request, each with a short reference (FU-050).

The reference goes back in the ``X-Request-Ref`` header and in every error envelope, so
an error seen in the browser ("ref 7f3a2c") leads straight to its log line. Unhandled
exceptions are logged here with their traceback and turned into a 500 envelope.
"""

from __future__ import annotations

import logging
import secrets
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from stats19.api.access import EDGE_HEADER

log = logging.getLogger("stats19.api")

REF_HEADER = "X-Request-Ref"
MAX_LOGGED_QUERY = 300  # filters are long JSON; enough to recognise the request
QUIET_PATHS = frozenset({"/api/health"})  # polled by monitors: log failures only


def new_ref() -> str:
    return secrets.token_hex(3)


def _target(request: Request) -> str:
    query = request.url.query
    if len(query) > MAX_LOGGED_QUERY:
        query = query[:MAX_LOGGED_QUERY] + "…"
    return request.url.path + (f"?{query}" if query else "")


def _server_error(ref: str) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "internal_error",
                "message": "Something went wrong on the server.",
                "ref": ref,
            },
        },
    )


def install_request_log(app: FastAPI) -> None:
    """Install last, so it wraps everything else (the access check included)."""

    @app.middleware("http")
    async def _log(request: Request, call_next):
        ref = new_ref()
        request.state.ref = ref
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("%s %s failed ref=%s", request.method, _target(request), ref)
            response = _server_error(ref)
        ms = (time.perf_counter() - start) * 1000
        response.headers[REF_HEADER] = ref
        status = response.status_code
        if status < 400 and request.url.path in QUIET_PATHS:
            return response
        log.log(
            logging.WARNING if status >= 500 else logging.INFO,
            "%s %s %d %.0fms ref=%s edge=%s",
            request.method,
            _target(request),
            status,
            ms,
            ref,
            request.headers.get(EDGE_HEADER, "-"),
        )
        return response
