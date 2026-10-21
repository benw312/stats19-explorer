"""POST /api/feedback: a user's problem, idea, question or praise, kept for triage (FU-055).

The browser sends what the user typed with the context it can see (the full URL, which
reproduces the screen, plus the app version, browser and window size, and the last error
reference shown). Who sent it comes from Access, or "LAN". It's stored in ``app.feedback``
(backed up daily with the schemes) and read with ``stats19 feedback``.

Writes go through stats19.api.writes: same-site JSON only, rate-limited, and the API role
may only insert here.
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from stats19.api.deps import get_conn
from stats19.api.envelope import ok
from stats19.api.org import current_org
from stats19.api.writes import check_write, editor, read_write

router = APIRouter()
log = logging.getLogger(__name__)

Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Org = Annotated[UUID, Depends(current_org)]

Kind = Literal["problem", "idea", "question", "liked"]
Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Kind = "problem"
    message: Message
    url: Annotated[str, Field(max_length=2000)]
    version: Annotated[str | None, Field(max_length=40)] = None
    user_agent: Annotated[str | None, Field(max_length=500)] = None
    viewport: Annotated[
        str | None, Field(max_length=40, pattern=r"^\d{1,5}×\d{1,5}( @\d(\.\d+)?x)?$")
    ] = None
    error_ref: Annotated[str | None, Field(pattern=r"^[0-9a-f]{6,12}$")] = None
    contact_ok: bool = True


@router.post("/feedback", status_code=201, dependencies=[Depends(check_write)])
def send_feedback(body: FeedbackIn, request: Request, conn: Conn, org: Org) -> dict:
    ref = getattr(request.state, "ref", None)
    with read_write(conn):
        row = conn.execute(
            """INSERT INTO app.feedback
                   (org_id, kind, message, url, version, user_agent, viewport, error_ref,
                    request_ref, contact_ok, created_by)
               VALUES (%(org)s, %(kind)s, %(message)s, %(url)s, %(version)s, %(user_agent)s,
                       %(viewport)s, %(error_ref)s, %(ref)s, %(contact_ok)s, %(who)s)
               RETURNING id""",
            body.model_dump() | {"org": org, "ref": ref, "who": editor(request)},
        ).fetchone()
    # the id and kind only: the message may hold anything, and stays in the database
    log.info("feedback received id=%s kind=%s", row["id"], body.kind)
    return ok({"id": row["id"], "ref": ref})
