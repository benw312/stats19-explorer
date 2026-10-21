"""/api/collisions: the filtered collisions as a sortable, paged table."""

from __future__ import annotations

from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, Query
from psycopg import sql

from stats19.api.deps import get_conn
from stats19.api.envelope import ok
from stats19.api.filters import Filter, collision_relation, compile_filter, filter_param

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Flt = Annotated[Filter, Depends(filter_param)]

Sort = Literal["date_desc", "date_asc", "severity", "casualties_desc"]
_ORDER = {
    "date_desc": "{a}.collision_date DESC, {a}.collision_time DESC NULLS LAST, {a}.collision_index",
    "date_asc": "{a}.collision_date, {a}.collision_time NULLS LAST, {a}.collision_index",
    "severity": "{a}.collision_severity, {a}.collision_date DESC, {a}.collision_index",
    "casualties_desc": (
        "{a}.number_of_casualties DESC, {a}.collision_date DESC, {a}.collision_index"
    ),
}

_COLUMNS = """d.collision_index, d.collision_date, d.collision_time,
       d.collision_severity AS severity, d.collision_severity_label AS severity_label,
       d.first_road_class_label, d.first_road_number, d.speed_limit,
       d.light_conditions_label, d.weather_conditions_label, d.road_surface_conditions_label,
       d.junction_detail_label, d.number_of_vehicles, d.number_of_casualties,
       ST_X(d.geom_wgs84) AS lon, ST_Y(d.geom_wgs84) AS lat"""


@router.get("/collisions")
def list_collisions(
    conn: Conn,
    flt: Flt,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    sort: Sort = "date_desc",
) -> dict:
    where, params = compile_filter(flt)
    rel = collision_relation(flt)
    total = conn.execute(
        sql.SQL("SELECT count(*) AS n FROM {rel} c WHERE {where}").format(rel=rel, where=where),
        params,
    ).fetchone()["n"]
    page_ids = [
        r["collision_index"]
        for r in conn.execute(
            sql.SQL(
                f"""SELECT c.collision_index FROM {{rel}} c WHERE {{where}}
                    ORDER BY {_ORDER[sort].format(a="c")}
                    LIMIT %(limit)s OFFSET %(offset)s"""
            ).format(rel=rel, where=where),
            params | {"limit": page_size, "offset": (page - 1) * page_size},
        )
    ]
    # Decode only this page (= ANY pushes into the decoded view; a join would not).
    rows = conn.execute(
        f"""SELECT {_COLUMNS} FROM mart.collision_decoded d
            WHERE d.collision_index = ANY(%(ids)s)
            ORDER BY {_ORDER[sort].format(a="d")}""",
        {"ids": page_ids},
    ).fetchall()
    return ok(rows, meta={"total": total, "page": page, "page_size": page_size})
