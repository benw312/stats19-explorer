"""/api/data-issues: DfT's documented data issues and our detected recording gaps (FU-049).

- ``/data-issues``: everything, for the About the data page.
- ``/data-issues/selection?f=``: the documented issues whose police force and years appear
  among the collisions matching the filter, so a figure can carry an asterisk.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends
from psycopg import sql

from stats19 import known_issues as ki
from stats19.api.deps import get_conn
from stats19.api.envelope import ok
from stats19.api.filters import Filter, collision_relation, compile_filter, filter_param
from stats19.reference.swap import tables_exist

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Flt = Annotated[Filter, Depends(filter_param)]

_FORCES = sorted({f for i in ki.ISSUES for f in i.police_forces})
_YEARS = (min(i.year_from for i in ki.ISSUES), max(i.year_to for i in ki.ISSUES))

_FORCE_YEARS = """
SELECT DISTINCT c.police_force, c.collision_year
FROM {rel} c
WHERE {where}
"""

_GAPS = """
SELECT y.code, a.name, a.region, y.year, round(y.recording_gap::numeric, 2)::float AS ratio
FROM geo.authority_year y JOIN geo.authority a USING (code)
WHERE y.recording_gap IS NOT NULL
ORDER BY y.year DESC, a.name
"""


def _issue_json(issue: ki.DataIssue, years: list[int] | None = None) -> dict:
    return asdict(issue) | ({"years": years} if years is not None else {})


def selection_issues(conn: psycopg.Connection, flt: Filter) -> list[dict]:
    """Documented issues touching the collisions that match the filter, with their years."""
    narrowed = (
        sql.SQL("c.police_force = ANY(%(issue_forces)s)"),
        sql.SQL("c.collision_year BETWEEN %(issue_y0)s AND %(issue_y1)s"),
    )
    where, params = compile_filter(flt, list(narrowed))
    rows = conn.execute(
        sql.SQL(_FORCE_YEARS).format(rel=collision_relation(flt), where=where),
        params | {"issue_forces": _FORCES, "issue_y0": _YEARS[0], "issue_y1": _YEARS[1]},
    ).fetchall()
    found = ki.issues_for((r["police_force"], r["collision_year"]) for r in rows)
    return [_issue_json(ki.BY_ID[i], years) for i, years in found.items()]


@router.get("/data-issues")
def data_issues(conn: Conn) -> dict:
    gaps = conn.execute(_GAPS).fetchall() if tables_exist(conn, "geo.authority_year") else []
    return ok(
        {
            "source_url": ki.SOURCE_URL,
            "source_updated": ki.SOURCE_UPDATED,
            "checked": ki.CHECKED,
            "issues": [_issue_json(i) for i in ki.ISSUES],
            "recording_gaps": gaps,
        }
    )


@router.get("/data-issues/selection")
def data_issues_selection(conn: Conn, flt: Flt) -> dict:
    return ok({"issues": selection_issues(conn, flt), "source_url": ki.SOURCE_URL})
