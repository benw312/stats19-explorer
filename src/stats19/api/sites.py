"""/api/sites: how sites overlap, for the site page header (PLAN-009 V3).

A cluster site lists the scored junctions and counted roads within its radius; a road
lists the junctions on it (those with an arm counted by the road's count point). Each
carries the risk layer's band, so the header can say which of them are worse than
similar sites.
"""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Query

from stats19.api.corridors import band_of
from stats19.api.deps import get_conn
from stats19.api.envelope import ok
from stats19.api.safety import BAND_SQL
from stats19.reference.swap import tables_exist

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]

MAX_NEAR = 12
MAX_NEAR_RADIUS_M = 2000

_POINT = "ST_Transform(ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326), 27700)"

_NEAR_JUNCTIONS = f"""
SELECT j.id, j.name, j.kind, j.motorway_junction, u.observed, u.excess, u.excess_rank,
       u.group_size, round(ST_Distance(j.geom_bng, {_POINT}))::int AS distance_m
FROM geo.junction j
JOIN geo.safety_unit u ON u.unit_type = 'junction' AND u.unit_id = j.id
WHERE ST_DWithin(j.geom_bng, {_POINT}, %(radius)s)
ORDER BY j.geom_bng <-> {_POINT}
LIMIT %(limit)s
"""

_NEAR_ROADS = f"""
SELECT p.count_point_id AS id, p.road_name, p.road_category, p.start_junction,
       p.end_junction, p.latest_aadf, p.latest_year, u.observed, u.excess, u.excess_rank,
       u.group_size, round(ST_Distance(s.geom_bng, {_POINT}))::int AS distance_m
FROM geo.traffic_stretch s
JOIN geo.traffic_count_point p USING (count_point_id)
LEFT JOIN geo.safety_unit u ON u.unit_type = 'link' AND u.unit_id = p.count_point_id::text
WHERE ST_DWithin(s.geom_bng, {_POINT}, %(radius)s) AND p.quality < 3
ORDER BY s.geom_bng <-> {_POINT}
LIMIT %(limit)s
"""

_ROAD_JUNCTIONS = """
SELECT DISTINCT ON (j.id) j.id, j.name, j.kind, j.motorway_junction, u.observed, u.excess,
       u.excess_rank, u.group_size
FROM geo.junction_arm a
JOIN geo.junction j ON j.id = a.junction_id
LEFT JOIN geo.safety_unit u ON u.unit_type = 'junction' AND u.unit_id = j.id
WHERE a.count_point_id = %(cp)s
ORDER BY j.id
"""


def _banded(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        r = dict(r)
        r["band"] = band_of(r.get("excess"), r.pop("excess_rank"), r.pop("group_size"))
        out.append(r)
    return out


def junctions_on_road(conn: psycopg.Connection, count_point_id: int) -> list[dict]:
    """Junctions with an arm counted by this count point, worst first."""
    if not tables_exist(conn, "geo.junction_arm", "geo.safety_unit"):
        return []
    rows = _banded(conn.execute(_ROAD_JUNCTIONS, {"cp": count_point_id}).fetchall())
    return sorted(rows, key=lambda r: (-(r["band"] if r["band"] is not None else -2), r["id"]))


@router.get("/sites/near")
def sites_near(
    conn: Conn,
    lon: Annotated[float, Query(ge=-9.0, le=3.0)],
    lat: Annotated[float, Query(ge=49.0, le=61.5)],
    radius_m: Annotated[int, Query(ge=10, le=MAX_NEAR_RADIUS_M)],
) -> dict:
    """Scored junctions and counted roads within radius_m of a point, nearest first."""
    if not tables_exist(conn, "geo.junction", "geo.safety_unit", "geo.traffic_stretch"):
        return ok({"available": False, "junctions": [], "roads": []})
    params = {"lon": lon, "lat": lat, "radius": radius_m, "limit": MAX_NEAR}
    return ok(
        {
            "available": True,
            "junctions": _banded(conn.execute(_NEAR_JUNCTIONS, params).fetchall()),
            "roads": _banded(conn.execute(_NEAR_ROADS, params).fetchall()),
        }
    )


_WORST_WITHIN = f"""
SELECT s.rank, w.unit_type, w.unit_id, w.name, w.excess, w.band
FROM unnest(%(ranks)s::int[], %(lons)s::float8[], %(lats)s::float8[], %(radii)s::float8[])
     AS s(rank, lon, lat, radius)
CROSS JOIN LATERAL (
    SELECT u.unit_type, u.unit_id, coalesce(j.name, p.road_name) AS name, u.excess,
           {BAND_SQL} AS band
    FROM geo.safety_unit u
    LEFT JOIN geo.junction j ON u.unit_type = 'junction' AND j.id = u.unit_id
    LEFT JOIN geo.traffic_count_point p
      ON u.unit_type = 'link' AND p.count_point_id::text = u.unit_id
    WHERE u.excess IS NOT NULL AND ST_DWithin(
        u.geom_bng,
        ST_Transform(ST_SetSRID(ST_MakePoint(s.lon, s.lat), 4326), 27700),
        s.radius)
    ORDER BY band DESC, u.excess DESC
    LIMIT 1
) w
WHERE w.band >= 1
"""


def worst_within(conn: psycopg.Connection, sites: list[dict]) -> dict[int, dict]:
    """For each cluster site, the scored junction or road inside it that is most worse than
    similar sites (worst 20% or worse), keyed by rank: the "in both" link for cluster rows.

    Junctions are points; a road is its count point's link midpoint, so a long link only
    counts when its midpoint falls in the circle.
    """
    if not sites or not tables_exist(conn, "geo.safety_unit", "geo.junction"):
        return {}
    rows = conn.execute(
        _WORST_WITHIN,
        {
            "ranks": [s["rank"] for s in sites],
            "lons": [s["lon"] for s in sites],
            "lats": [s["lat"] for s in sites],
            "radii": [float(s["radius_m"]) for s in sites],
        },
    ).fetchall()
    keys = ("unit_type", "unit_id", "name", "excess", "band")
    out = {}
    for row in rows:  # positional: works with tuple and dict row factories
        rank, *values = row.values() if isinstance(row, dict) else row
        out[rank] = dict(zip(keys, values, strict=True))
    return out
