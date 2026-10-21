"""POST /api/client-errors: the web app reports its own crashes to the API log (FU-050).

Errors in the browser otherwise leave no trace on the server. The browser makes up the
reference (shown to the user straight away, e.g. on the crash screen) and sends it here,
so the log line can be found from a screenshot. Nothing is stored: it's a log line.

A global rate limit keeps a crash loop (or anyone else) from flooding the log.
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from stats19.api.envelope import ApiError, ok
from stats19.api.limits import RateLimit

router = APIRouter()
log = logging.getLogger("stats19.client")

MAX_PER_WINDOW = 30
WINDOW_S = 300.0
MAX_STACK_LINES = 15


LIMIT = RateLimit(MAX_PER_WINDOW, WINDOW_S)


class ClientError(BaseModel):
    ref: Annotated[str, Field(pattern=r"^[0-9a-f]{6}$")]
    kind: Literal["error", "unhandledrejection", "render"]
    message: Annotated[str, Field(max_length=500)]
    stack: Annotated[str | None, Field(max_length=4000)] = None
    url: Annotated[str, Field(max_length=500)]
    version: Annotated[str, Field(max_length=40)]


def _one_line(text: str) -> str:
    """Keep a reported value on one log line, so it can't fake other log lines."""
    return " ".join(text.split())


def _stack(text: str | None) -> str:
    if not text:
        return ""
    lines = [_one_line(line) for line in text.splitlines() if line.strip()]
    return "".join(f"\n    {line}" for line in lines[:MAX_STACK_LINES])


@router.post("/client-errors")
def report(body: ClientError) -> dict:
    if not LIMIT.allow():
        raise ApiError(429, "rate_limited", "Too many error reports; this one wasn't logged.")
    log.warning(
        "browser %s ref=%s version=%s url=%s: %s%s",
        body.kind,
        body.ref,
        _one_line(body.version),
        _one_line(body.url),
        _one_line(body.message),
        _stack(body.stack),
    )
    return ok({"ref": body.ref})
