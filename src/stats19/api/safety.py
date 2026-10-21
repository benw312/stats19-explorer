"""/api/safety: how a road or junction compares with similar ones (PLAN-008 T4).

Each site's predicted collisions come from its peer group's safety performance function;
Empirical Bayes blends that with the site's own count; *excess* is the difference. Ranking
by excess picks the sites that stay worse than similar ones (validated out of sample: the
top 2% by excess in 2016-20 had the most excess collisions in 2021-25, more than ranking by
raw counts or raw rates).

Excess collisions are valued at DfT's average value of prevention (RAS4001), using the peer
group's severity mix, so the card can say what the excess costs each year and work out a
scheme's first-year rate of return. The map layer colours each site by where its excess
ranks among similar sites in its region (London, Scotland, Wales or the rest of England:
regions record collisions at very different rates).
"""

from __future__ import annotations

from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, Path, Query, Response
from fastapi.exceptions import RequestValidationError
from psycopg import sql

from stats19.api.deps import get_conn
from stats19.api.envelope import ok
from stats19.api.filters import Filter, area_condition, filter_param
from stats19.api.prevention import prevention_values, value_per_collision
from stats19.api.tiles import MVT_MEDIA_TYPE
from stats19.reference.safety_build import SAFETY_YEARS
from stats19.reference.swap import tables_exist

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Flt = Annotated[Filter, Depends(filter_param)]

MAX_TOP = 100

_GROUP_TOTALS = "m.observed_total, m.ksi_total, m.fatal_total"

_UNIT = f"""
SELECT u.peer_group, u.urban, u.region, u.observed, u.ksi, u.predicted, u.eb, u.excess,
       u.excess, u.excess_per_km, u.excess_rank, u.group_size, u.length_km, u.flow,
       u.flow_estimated, u.flag,
       {_GROUP_TOTALS}
FROM geo.safety_unit u
LEFT JOIN geo.safety_model m ON m.unit_type = u.unit_type AND m.peer_group = u.peer_group
WHERE u.unit_type = %s AND u.unit_id = %s
"""


def _period(conn: psycopg.Connection) -> tuple[int, int] | None:
    latest = conn.execute("SELECT max(collision_year) AS y FROM core.collision").fetchone()["y"]
    return None if latest is None else (latest - SAFETY_YEARS + 1, latest)


def with_value(row: dict, values: dict[int, float]) -> dict:
    """Replace the group's severity totals with the value of one of its collisions."""
    totals = (row.pop("observed_total"), row.pop("ksi_total"), row.pop("fatal_total"))
    vpc = None if totals[0] is None else value_per_collision(*totals, values)
    return row | {"value_per_collision": None if vpc is None else round(vpc)}


def safety_for(conn: psycopg.Connection, unit_type: str, unit_id: str) -> dict | None:
    """The comparison block for a card, or None when the site isn't scored."""
    if not tables_exist(conn, "geo.safety_unit", "geo.safety_model", "core.collision"):
        return None
    row = conn.execute(_UNIT, (unit_type, unit_id)).fetchone()
    period = _period(conn)
    if row is None or period is None:
        return None
    price_year, values = prevention_values(conn)
    return with_value(row, values) | {
        "year_from": period[0],
        "year_to": period[1],
        "years": SAFETY_YEARS,
        "price_year": price_year,
    }


_TOP = f"""
SELECT u.unit_type, u.unit_id, u.peer_group, u.region, u.observed, u.ksi, u.predicted, u.eb,
       u.excess, u.excess_per_km, u.excess_rank, u.group_size, u.length_km, u.flow,
       u.flow_estimated, u.flag,
       {_GROUP_TOTALS}, coalesce(j.name, p.road_name) AS name, j.kind, j.motorway_junction,
       p.road_category, p.start_junction, p.end_junction,
       ST_X(ST_Transform(u.geom_bng, 4326)) AS lon, ST_Y(ST_Transform(u.geom_bng, 4326)) AS lat
FROM (SELECT * FROM geo.safety_unit c WHERE {{area}}) u
LEFT JOIN geo.safety_model m ON m.unit_type = u.unit_type AND m.peer_group = u.peer_group
LEFT JOIN geo.junction j ON u.unit_type = 'junction' AND j.id = u.unit_id
LEFT JOIN geo.traffic_count_point p
  ON u.unit_type = 'link' AND p.count_point_id::text = u.unit_id
WHERE u.unit_type = %(unit)s AND u.excess IS NOT NULL
ORDER BY u.{{order}} DESC NULLS LAST, u.unit_id
LIMIT %(limit)s
"""


@router.get("/safety/top")
def safety_top(
    conn: Conn,
    flt: Flt,
    unit: Literal["link", "junction"] = "junction",
    sort: Literal["excess", "excess_per_km"] = "excess",
    limit: Annotated[int, Query(ge=1, le=MAX_TOP)] = 20,
) -> dict:
    """The sites in the filter's area that are most worse than similar sites."""
    if not tables_exist(conn, "geo.safety_unit", "geo.safety_model", "core.collision"):
        return ok({"available": False, "sites": []})
    # area_condition filters the alias c directly, so it can use the spatial index (FU-052)
    area, params = area_condition(flt.area) if flt.area is not None else (sql.SQL("TRUE"), {})
    order = sort if unit == "link" else "excess"
    rows = conn.execute(
        sql.SQL(_TOP).format(area=area, order=sql.Identifier(order)),
        params | {"unit": unit, "limit": limit},
    ).fetchall()
    period = _period(conn)
    price_year, values = prevention_values(conn)
    return ok(
        {
            "available": True,
            "unit": unit,
            "sort": order,
            "year_from": period[0] if period else None,
            "year_to": period[1] if period else None,
            "years": SAFETY_YEARS,
            "price_year": price_year,
            "sites": [with_value(r, values) for r in rows],
        }
    )


# ------------------------------------------------------------------ map layer

# Where a site's excess ranks among similar sites: 3 = worst 1%, 2 = worst 5%, 1 = worst
# 20%, 0 = middle, -1 = best 20%. The same cut-offs as the card's wording.
BAND_SQL = """
CASE WHEN u.excess > 0 AND u.excess_rank <= 0.01 * u.group_size THEN 3
     WHEN u.excess > 0 AND u.excess_rank <= 0.05 * u.group_size THEN 2
     WHEN u.excess > 0 AND u.excess_rank <= 0.20 * u.group_size THEN 1
     WHEN u.excess_rank > 0.80 * u.group_size THEN -1
     ELSE 0 END"""

JUNCTION_ZOOM = 9  # junctions are dense: worst 5% from here, worst 20% from 13, all from 15
_ENV = "ST_TileEnvelope(%(z)s, %(x)s, %(y)s)"
_MARGIN_ENV = "ST_TileEnvelope(%(z)s, %(x)s, %(y)s, margin => 64.0 / 4096)"

_LINK_TILE = f"""
SELECT ST_AsMVT(t, 'risk_links', 4096, 'geom') FROM (
    SELECT p.count_point_id AS id, {BAND_SQL} AS band,
           ST_AsMVTGeom(ST_Simplify(s.geom_3857, %(px)s), {_ENV}, 4096, 64, true) AS geom
    FROM geo.traffic_stretch s
    JOIN geo.traffic_count_point p USING (count_point_id)
    JOIN geo.safety_unit u ON u.unit_type = 'link' AND u.unit_id = s.count_point_id::text
    WHERE s.method = 'major' AND s.geom_3857 && {_MARGIN_ENV} AND u.excess IS NOT NULL
    ORDER BY band
) t WHERE t.geom IS NOT NULL
"""

_JUNCTION_TILE = f"""
SELECT ST_AsMVT(t, 'risk_junctions', 4096, 'geom') FROM (
    SELECT j.id, {BAND_SQL} AS band,
           ST_AsMVTGeom(j.geom_3857, {_ENV}, 4096, 64, true) AS geom
    FROM geo.junction j
    JOIN geo.safety_unit u ON u.unit_type = 'junction' AND u.unit_id = j.id
    WHERE j.geom_3857 && {_MARGIN_ENV} AND u.excess IS NOT NULL
    ORDER BY band
) t WHERE t.geom IS NOT NULL AND t.band >= %(min_band)s
"""


def junction_min_band(z: int) -> int | None:
    """The least band of junction drawn at zoom z (None: no junctions)."""
    if z < JUNCTION_ZOOM:
        return None
    if z < 13:
        return 2
    if z < 15:
        return 1
    return -1


def _tile_bytes(conn: psycopg.Connection, query: str, params: dict) -> bytes:
    row = conn.execute(query, params).fetchone()
    return bytes(next(iter(row.values()))) if row else b""


@router.get("/safety/tiles/{z}/{x}/{y}.mvt")
def safety_tile(
    conn: Conn,
    z: Annotated[int, Path(ge=0, le=22)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
) -> Response:
    """Roads (count point links) and junctions coloured by excess against similar sites."""
    if x >= 2**z or y >= 2**z:
        raise RequestValidationError([{"loc": ("path", "x/y"), "msg": "outside tile grid"}])
    body = b""
    needed = ("geo.safety_unit", "geo.traffic_stretch", "geo.junction")
    if z >= 5 and tables_exist(conn, *needed):
        params = {"z": z, "x": x, "y": y, "px": 40075016.0 / (4096 * 2**z)}
        body = _tile_bytes(conn, _LINK_TILE, params)
        min_band = junction_min_band(z)
        if min_band is not None:
            body += _tile_bytes(conn, _JUNCTION_TILE, params | {"min_band": min_band})
    return Response(
        content=body, media_type=MVT_MEDIA_TYPE, headers={"Cache-Control": "public, max-age=600"}
    )
