"""Reading and triaging the feedback users send from the app (FU-055).

Run on the server with the owner's connection: ``stats19 feedback`` lists new and seen
items, ``--seen ID`` / ``--done ID`` move one along, with an optional ``--note``.
"""

from __future__ import annotations

import textwrap

import psycopg

KIND_LABELS = {"problem": "Problem", "idea": "Idea", "question": "Question", "liked": "Liked"}
WIDTH = 88


def _has_table(conn: psycopg.Connection) -> bool:
    return conn.execute("SELECT to_regclass('app.feedback')").fetchone()[0] is not None


def list_items(
    conn: psycopg.Connection, include_done: bool = False, limit: int = 50
) -> list[tuple]:
    """Newest first: (id, created_at, kind, status, created_by, contact_ok, url, version,
    viewport, user_agent, error_ref, request_ref, message, note)."""
    if not _has_table(conn):
        return []
    return conn.execute(
        """SELECT id, created_at, kind, status, created_by, contact_ok, url, version, viewport,
                  user_agent, error_ref, request_ref, message, note
           FROM app.feedback
           WHERE %(all)s OR status <> 'done'
           ORDER BY created_at DESC LIMIT %(limit)s""",
        {"all": include_done, "limit": limit},
    ).fetchall()


def set_status(conn: psycopg.Connection, item: int, status: str, note: str | None) -> bool:
    """Mark an item seen or done, keeping any earlier note unless a new one is given."""
    if status not in ("seen", "done"):
        raise ValueError(f"unknown status {status!r}")
    if not _has_table(conn):
        return False
    with conn.transaction():
        row = conn.execute(
            """UPDATE app.feedback SET status = %s, note = coalesce(%s, note)
               WHERE id = %s RETURNING id""",
            (status, note, item),
        ).fetchone()
    return row is not None


def count_new(conn: psycopg.Connection) -> int:
    if not _has_table(conn):
        return 0
    return conn.execute("SELECT count(*) FROM app.feedback WHERE status = 'new'").fetchone()[0]


def format_items(rows: list[tuple]) -> str:
    """A readable block per item: who, when, where, then the message."""
    blocks = []
    for (
        item,
        created,
        kind,
        status,
        who,
        contact_ok,
        url,
        version,
        viewport,
        agent,
        error_ref,
        request_ref,
        message,
        note,
    ) in rows:
        head = (
            f"#{item}  {KIND_LABELS.get(kind, kind)}  [{status}]  {created:%Y-%m-%d %H:%M}  "
            f"{who}{'' if contact_ok else ' (no contact)'}"
        )
        context = [f"url: {url}"]
        context.append(
            "  ".join(
                part
                for part in (
                    f"version {version}" if version else "",
                    f"window {viewport}" if viewport else "",
                    f"error ref {error_ref}" if error_ref else "",
                    f"request ref {request_ref}" if request_ref else "",
                )
                if part
            )
        )
        if agent:
            context.append(f"browser: {agent}")
        body = textwrap.fill(
            " ".join(message.split()), WIDTH, initial_indent="  ", subsequent_indent="  "
        )
        lines = [head, *(f"  {c}" for c in context if c), body]
        if note:
            lines.append(f"  note: {note}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
