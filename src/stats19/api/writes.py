"""Safeguards for the API's few writes, all into the ``app`` schema (PLAN-011 §5).

- **Only same-site JSON.** A write must send an ``Origin`` naming the host it was sent to,
  and its body as ``Content-Type: application/json``. A page on another site can't send
  JSON, PUT or DELETE without a CORS preflight, which the API never answers, so it can't
  make a signed-in browser write here (CSRF).
- **Rate-limited,** across all clients, like the browser error reports.
- **Read-only unless asked.** The API's role starts every transaction read-only (migration
  004). ``read_write`` opens one that may write, and the role may write only to ``app``.
- **Stamped with who.** The Cloudflare Access email for remote edits, or "LAN".
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlsplit

import psycopg
from fastapi import Request
from psycopg.pq import TransactionStatus

from stats19.api.envelope import ApiError
from stats19.api.limits import RateLimit

MAX_WRITES = 120
WINDOW_S = 300.0
LIMIT = RateLimit(MAX_WRITES, WINDOW_S)

LAN_EDITOR = "LAN"


def check_write(request: Request) -> None:
    """Dependency for every write endpoint."""
    content_type = request.headers.get("content-type", "")
    has_body = request.method in ("POST", "PUT", "PATCH")  # a DELETE sends no body
    if has_body and content_type.split(";")[0].strip().lower() != "application/json":
        raise ApiError(415, "unsupported_media_type", "Send the data as JSON.")
    origin = request.headers.get("origin")
    host = request.headers.get("host")
    if not origin or not host or urlsplit(origin).netloc.lower() != host.lower():
        raise ApiError(403, "cross_origin", "Changes can only be made from the app itself.")
    if not LIMIT.allow():
        raise ApiError(429, "rate_limited", "Too many changes at once. Try again in a minute.")


def editor(request: Request) -> str:
    """Who made a change: the Access email (set by stats19.api.access) or "LAN"."""
    return getattr(request.state, "access_email", None) or LAN_EDITOR


@contextmanager
def read_write(conn: psycopg.Connection) -> Iterator[None]:
    """A transaction that may write. It must be the request's first: a transaction that
    has already run a query stays read-only, so that's refused rather than half-working."""
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise RuntimeError("read_write must start the request's first transaction")
    with conn.transaction():
        conn.execute("SET TRANSACTION READ WRITE")
        yield
