"""/api/junctions: junctions built from OS Open Roads, their flows and collisions (PLAN-008 T3).

Exposure follows COBALT and the Highway Safety Manual: vehicles **entering** the junction.
DfT's AADF is two-way, so each counted arm contributes half its AADF; both sides of a
through road are separate arms, so a road passing a T-junction counts once in full. The
major-road and minor-road parts are kept apart, because most minor arms have no count.
"""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Path, Query, Response
from fastapi.exceptions import RequestValidationError
from psycopg import sql

from stats19.api.deps import get_conn
from stats19.api.envelope import NotFound, ok
from stats19.api.filters import (
    MAX_COLLISION_IDS,
    Filter,
    collision_relation,
    compile_filter,
    filter_param,
    parse_filter,
)
from stats19.api.safety import safety_for
from stats19.api.tiles import MVT_MEDIA_TYPE
from stats19.reference.junction_build import COLLISION_RADIUS_M, COLLISION_YEARS

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Flt = Annotated[Filter, Depends(filter_param)]

MAJOR_JUNCTION_ZOOM = 13  # junctions on motorways, A and B roads
CLASSIFIED_JUNCTION_ZOOM = 14  # ...and C roads
ALL_JUNCTION_ZOOM = 15  # ...and every other junction
DEFAULT_YEARS = 5
DAYS_PER_YEAR = 365

KIND_LABEL = {
    "roundabout": "Roundabout",
    "mini_roundabout": "Mini-roundabout",
    "t_junction": "T or Y junction",
    "crossroads": "Crossroads",
    "multi_arm": "Junction with more than four arms",
}


def class_filter(z: int) -> str:
    """Which junctions a tile at zoom z includes (internal constants only)."""
    if z >= ALL_JUNCTION_ZOOM:
        return "TRUE"
    classes = ["Motorway", "A Road", "B Road"]
    if z >= CLASSIFIED_JUNCTION_ZOOM:
        classes.append("Classified Unnumbered")
    return "j.top_class IN (" + ", ".join(f"'{c}'" for c in classes) + ")"


def junctions_available(conn: psycopg.Connection) -> bool:
    row = conn.execute(
        """SELECT to_regclass('geo.junction') IS NOT NULL
                  AND to_regclass('geo.junction_collision') IS NOT NULL AS ok"""
    ).fetchone()
    return bool(row["ok"])


_TILE = """
SELECT ST_AsMVT(t, 'junctions', 4096, 'geom') FROM (
    SELECT j.id, j.kind, j.arms, j.signalised, coalesce(n.n, 0) AS n,
           ST_AsMVTGeom(j.geom_3857, ST_TileEnvelope(%(z)s, %(x)s, %(y)s), 4096, 64, true)
               AS geom
    FROM geo.junction j
    LEFT JOIN LATERAL (
        SELECT count(*) AS n
        FROM geo.junction_collision jc JOIN {rel} c ON c.collision_index = jc.collision_index
        WHERE jc.junction_id = j.id AND {where}
    ) n ON true
    WHERE j.geom_3857 && ST_TileEnvelope(%(z)s, %(x)s, %(y)s, margin => 64.0 / 4096)
      AND {classes}
    ORDER BY n.n NULLS FIRST
) t WHERE t.geom IS NOT NULL
"""


@router.get("/junctions/tiles/{z}/{x}/{y}.mvt")
def junction_tile(
    conn: Conn,
    z: Annotated[int, Path(ge=0, le=22)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
    f: Annotated[str | None, Query(max_length=20_000)] = None,
) -> Response:
    """Junction points from z13, each with the number of its collisions matching the filter."""
    if x >= 2**z or y >= 2**z:
        raise RequestValidationError([{"loc": ("path", "x/y"), "msg": "outside tile grid"}])
    body = b""
    if z >= MAJOR_JUNCTION_ZOOM and junctions_available(conn):
        flt = parse_filter(f)
        where, params = compile_filter(flt)
        query = sql.SQL(_TILE).format(
            rel=collision_relation(flt), where=where, classes=sql.SQL(class_filter(z))
        )
        row = conn.execute(query, params | {"z": z, "x": x, "y": y}).fetchone()
        body = bytes(next(iter(row.values()))) if row else b""
    return Response(
        content=body, media_type=MVT_MEDIA_TYPE, headers={"Cache-Control": "public, max-age=600"}
    )


# ------------------------------------------------------------------ detail

_JUNCTION = """
SELECT id, kind, arms, name, top_class, signals, signalised, motorway_junction, nodes,
       ST_X(ST_Transform(geom_bng, 4326)) AS lon, ST_Y(ST_Transform(geom_bng, 4326)) AS lat,
       ST_AsGeoJSON(ST_Transform(match_geom, 4326), 6)::json AS geometry,
       -- the ground collisions are matched within: what a scheme here saves (V5)
       ST_AsGeoJSON(ST_Transform(ST_Buffer(match_geom, %s, 8), 4326), 6)::json AS match_area
FROM geo.junction WHERE id = %s
"""

_ARMS = """
SELECT a.arm, a.role, a.road_class, a.road_number, a.name, a.form_of_way, a.bearing,
       a.count_point_id, p.road_name AS count_road, p.road_type AS count_road_type,
       p.latest_aadf, p.latest_year, p.last_counted_year, p.quality,
       coalesce(
           (SELECT round(avg(f.all_motor_vehicles))::integer FROM geo.traffic_aadf f
            WHERE f.count_point_id = a.count_point_id
              AND f.year BETWEEN %(year_from)s AND %(year_to)s),
           p.latest_aadf) AS period_aadf  -- the period's mean flow, else the latest
FROM geo.junction_arm a
LEFT JOIN geo.traffic_count_point p ON p.count_point_id = a.count_point_id
WHERE a.junction_id = %(id)s ORDER BY a.arm
"""


def entering_flow(arms: list[dict], key: str = "aadf") -> dict:
    """Vehicles entering per day, from each arm's two-way AADF (half of it enters).

    ``coverage``: 'all' arms counted; 'major' when only minor arms lack a count (the usual
    case: exposure, and so the rate, is a little understated / overstated respectively);
    'partial' when a major arm has no count (no rate is given).
    """
    major = [a for a in arms if a["role"] == "major"]
    minor = [a for a in arms if a["role"] == "minor"]

    def half(group: list[dict]) -> float:
        return sum(a[key] for a in group if a[key] is not None) / 2

    uncounted_major = sum(a[key] is None for a in major)
    uncounted_minor = sum(a[key] is None for a in minor)
    coverage = "partial" if uncounted_major else ("major" if uncounted_minor else "all")
    return {
        "entering": round(half(major) + half(minor)),
        "major": round(half(major)),
        "minor": round(half(minor)),
        "uncounted_major": uncounted_major,
        "uncounted_minor": uncounted_minor,
        "coverage": coverage,
    }


def collision_period(conn: psycopg.Connection, flt: Filter) -> tuple[int, int, int] | None:
    """(from, to, latest) years: the filter's, else the last DEFAULT_YEARS, within the
    years collisions are matched to junctions."""
    latest = conn.execute("SELECT max(collision_year) AS y FROM core.collision").fetchone()["y"]
    if latest is None:
        return None
    first = latest - COLLISION_YEARS + 1
    year_to = min(flt.year_to or latest, latest)
    year_from = max(flt.year_from or (year_to - DEFAULT_YEARS + 1), first)
    return year_from, year_to, latest


# STATS19 junction_control codes -> the card's wording (0 / -1 / 9 are left out)
RECORDED_CONTROL = {1: "authorised_person", 2: "signals", 3: "stop", 4: "give_way"}
_SEVERITY_KEY = {1: "fatal", 2: "serious", 3: "slight"}


def summarise_collisions(rows: list[dict], year_from: int, year_to: int) -> dict:
    """Totals, per-year severity counts (every year in the period) and recorded control."""
    totals = {k: sum(r["severity"] == s for r in rows) for s, k in _SEVERITY_KEY.items()}
    by_year = [
        {"year": y}
        | {
            k: sum(r["year"] == y and r["severity"] == s for r in rows)
            for s, k in _SEVERITY_KEY.items()
        }
        for y in range(year_from, year_to + 1)
    ]
    control = {
        name: sum(r["control"] == code for r in rows) for code, name in RECORDED_CONTROL.items()
    }
    return {
        "total": len(rows),
        **totals,
        "by_year": by_year,
        "recorded_control": control,
        "ids": [r["collision_index"] for r in rows[:MAX_COLLISION_IDS]],
        "year_from": year_from,
        "year_to": year_to,
    }


def _collisions(conn: psycopg.Connection, flt: Filter, junction_id: str) -> list[dict]:
    where, params = compile_filter(flt)
    rel = collision_relation(flt)
    return conn.execute(
        sql.SQL(
            """SELECT c.collision_index, c.collision_year AS year,
                      c.collision_severity AS severity, c.junction_control AS control
               FROM geo.junction_collision jc
               JOIN {rel} c ON c.collision_index = jc.collision_index
               WHERE jc.junction_id = %(junction_id)s AND {where}
               ORDER BY c.collision_year DESC, c.collision_index"""
        ).format(rel=rel, where=where),
        params | {"junction_id": junction_id},
    ).fetchall()


def collision_rate(collisions: int, entering_per_day: float, years: int) -> dict | None:
    """Collisions per million vehicles entering (COBALT's junction rate)."""
    if entering_per_day <= 0 or years <= 0:
        return None
    mve = entering_per_day * DAYS_PER_YEAR * years / 1e6
    return {"per_mve": round(collisions / mve, 3), "mve": round(mve, 2)}


@router.get("/junctions/{junction_id}")
def junction(
    conn: Conn, flt: Flt, junction_id: Annotated[str, Path(pattern=r"^[0-9A-Za-z_-]{1,64}$")]
) -> dict:
    if not junctions_available(conn):
        raise NotFound("junctions are not loaded")
    row = conn.execute(_JUNCTION, (COLLISION_RADIUS_M, junction_id)).fetchone()
    if row is None:
        raise NotFound(f"no junction {junction_id}")
    period = collision_period(conn, flt)
    year_from, year_to, latest = period or (None, None, None)
    arms = conn.execute(
        _ARMS, {"id": junction_id, "year_from": year_from or 0, "year_to": year_to or 0}
    ).fetchall()
    arms = [a | {"aadf": a["latest_aadf"]} for a in arms]
    flow = entering_flow(arms) | {"year": max((a["latest_year"] or 0 for a in arms), default=0)}
    collisions, rate = None, None
    if period is not None:
        scoped = flt.model_copy(update={"year_from": year_from, "year_to": year_to})
        collisions = summarise_collisions(
            _collisions(conn, scoped, junction_id), year_from, year_to
        )
        period_flow = entering_flow([a | {"aadf": a["period_aadf"]} for a in arms])
        if period_flow["coverage"] != "partial":
            rate = collision_rate(
                collisions["total"], period_flow["entering"], year_to - year_from + 1
            )
            if rate is not None:
                rate |= {"coverage": period_flow["coverage"], "entering": period_flow["entering"]}
    return ok(
        row
        | {
            "kind_label": KIND_LABEL.get(row["kind"], row["kind"]),
            "arm_list": arms,
            "flow": flow,
            "collisions": collisions,
            "rate": rate,
            "safety": safety_for(conn, "junction", junction_id),
            "matching": {
                "radius_m": COLLISION_RADIUS_M,
                "years": COLLISION_YEARS,
                "latest_year": latest,
            },
        }
    )
