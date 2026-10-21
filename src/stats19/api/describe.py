"""Plain-English description of a Filter, for exports, reports and the UI."""

from __future__ import annotations

import json
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends

from stats19.api.deps import get_conn
from stats19.api.envelope import ok
from stats19.api.filters import (
    AuthorityArea,
    FieldCondition,
    Filter,
    PolygonArea,
    RadiusArea,
    filter_param,
)

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Flt = Annotated[Filter, Depends(filter_param)]

SEVERITY_NAMES = {1: "Fatal", 2: "Serious", 3: "Slight"}
ROAD_USER_NAMES = {
    "pedestrian": "Pedestrian",
    "pedal_cycle": "Pedal cycle",
    "motorcycle": "Motorcycle",
    "bus": "Bus or coach",
    "goods_heavy": "HGV (over 3.5 t)",
    "ppt": "E-scooter / personal powered transporter",
    "mobility_scooter": "Mobility scooter",
    "horse": "Ridden horse",
}
AREA_TYPE_NAMES = {
    "highway_authority": "Highway authority",
    "district": "District",
    "police_force": "Police force area",
}


def field_title(field: str) -> str:
    return field.replace("_", " ").capitalize()


def _labels(conn: psycopg.Connection, table: str, field: str, codes: list[int]) -> list[str]:
    found = {
        r["code"]: r["label"]
        for r in conn.execute(
            """SELECT code, label FROM core.lookup_code
               WHERE table_name = %s AND field_name = %s AND code = ANY(%s)""",
            (table, field, [str(c) for c in codes]),
        )
    }
    return [found.get(str(c), str(c)) for c in codes]


def _condition(conn: psycopg.Connection, cond: FieldCondition) -> str:
    title = field_title(cond.field)
    if cond.table != "collision":
        title = f"{title} ({cond.table})"
    if cond.op == "between":
        lo, hi = sorted(cond.values)
        return f"{title}: {lo}–{hi}"
    labels = _labels(conn, cond.table, cond.field, cond.values)
    if cond.field == "speed_limit":
        labels = [f"{v} mph" for v in cond.values]
    prefix = "not " if cond.op == "not_in" else ""
    return f"{title}: {prefix}{', '.join(labels)}"


def _area(conn: psycopg.Connection, area) -> str:
    if isinstance(area, RadiusArea):
        return f"Area: within {area.radius_m:,} m of {area.lat:.5f}, {area.lon:.5f}"
    if isinstance(area, PolygonArea):
        km2 = conn.execute(
            """SELECT ST_Area(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 27700))
               / 1e6 AS km2""",
            (json.dumps(area.geometry),),
        ).fetchone()["km2"]
        return f"Area: drawn boundary ({km2:,.2f} km²)"
    assert isinstance(area, AuthorityArea)
    row = conn.execute(
        "SELECT name FROM geo.boundary WHERE boundary_type = %s AND code = %s",
        (area.boundary_type, area.code),
    ).fetchone()
    name = row["name"] if row else area.code
    return f"Area: {AREA_TYPE_NAMES[area.boundary_type]} {name} ({area.code})"


def describe_filter(conn: psycopg.Connection, f: Filter) -> list[str]:
    lines: list[str] = []
    if f.year_from is not None and f.year_to is not None:
        lines.append(f"Years: {f.year_from}–{f.year_to}")
    elif f.year_from is not None:
        lines.append(f"From {f.year_from}")
    elif f.year_to is not None:
        lines.append(f"Up to {f.year_to}")
    if f.date_from or f.date_to:
        lines.append(f"Dates: {f.date_from or '…'} to {f.date_to or '…'}")
    if f.severity:
        lines.append("Severity: " + ", ".join(SEVERITY_NAMES[s] for s in sorted(f.severity)))
    if f.involves:
        lines.append(
            "Road users involved: " + ", ".join(ROAD_USER_NAMES.get(g, g) for g in f.involves)
        )
    if f.day_of_week:
        lines.append(
            "Day of week: "
            + ", ".join(_labels(conn, "collision", "day_of_week", sorted(f.day_of_week)))
        )
    if f.time_from and f.time_to:
        lines.append(f"Time of day: {f.time_from:%H:%M}–{f.time_to:%H:%M}")
    lines += [_condition(conn, c) for c in f.fields]
    if f.area is not None:
        lines.append(_area(conn, f.area))
    if f.collision_ids is not None:
        n = len(f.collision_ids)
        lines.append(f"Collisions: {n:,} selected individually")
    return lines or ["All collisions"]


@router.get("/describe")
def describe(conn: Conn, flt: Flt) -> dict:
    return ok(describe_filter(conn, flt))
