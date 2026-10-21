"""/api/traffic: DfT traffic counts (AADF) as map tiles, count-point detail and area summary.

Standalone traffic module (PLAN-008 T1): flows are shown as published, with how reliable each
figure is (``quality``: 0 counted in the latest year, 1 estimated from a recent count,
2 estimated from an old count, 3 no longer in the published data).
"""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Path, Response
from fastapi.exceptions import RequestValidationError
from psycopg import sql

from stats19.api.deps import get_conn
from stats19.api.envelope import NotFound, ok
from stats19.api.filters import (
    Area,
    AuthorityArea,
    Filter,
    area_condition,
    area_geometry,
    filter_param,
)
from stats19.api.link_collisions import link_collisions
from stats19.api.safety import safety_for
from stats19.api.sites import junctions_on_road
from stats19.api.tiles import MVT_MEDIA_TYPE
from stats19.marts import WEB_MERCATOR_WIDTH

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Flt = Annotated[Filter, Depends(filter_param)]

STRATEGIC_ONLY_BELOW_ZOOM = 7  # national view: motorways and trunk A roads only
MAJOR_ONLY_BELOW_ZOOM = 8  # then all major roads
CURRENT_ONLY_BELOW_ZOOM = 10  # historic (no longer counted) points appear from here
LINK_ZOOM = 9  # the roads each count applies to appear from here (major roads)
MINOR_LINK_ZOOM = 12  # minor-road stretches (short, many) from here
TOP_POINTS = 10
DFT_COUNT_POINT_URL = "https://roadtraffic.dft.gov.uk/count-points/{id}"

ROAD_CATEGORY = {
    "TM": "Trunk motorway",
    "PM": "Principal motorway",
    "TA": "Trunk A road",
    "PA": "Principal A road",
    "MB": "B road",
    "MCU": "C or unclassified road",
}

VEHICLE_FIELDS = (
    "pedal_cycles",
    "two_wheeled_motor_vehicles",
    "cars_and_taxis",
    "buses_and_coaches",
    "lgvs",
    "all_hgvs",
    "all_motor_vehicles",
)


def point_filter(z: int) -> str:
    """Which count points a tile at zoom z includes (internal constants only)."""
    if z < STRATEGIC_ONLY_BELOW_ZOOM:
        return "p.road_category IN ('TM', 'PM', 'TA') AND p.quality < 3"
    if z < MAJOR_ONLY_BELOW_ZOOM:
        return "p.road_type = 'Major' AND p.quality < 3"
    if z < CURRENT_ONLY_BELOW_ZOOM:
        return "p.quality < 3"
    return "TRUE"


_POINTS = """
SELECT ST_AsMVT(t, 'traffic_points', 4096, 'geom') FROM (
    SELECT p.count_point_id AS id, p.latest_aadf AS aadf, p.road_type AS type, p.quality,
           ST_AsMVTGeom(p.geom_3857, ST_TileEnvelope(%(z)s, %(x)s, %(y)s), 4096, 64, true) AS geom
    FROM geo.traffic_count_point p
    WHERE p.geom_3857 && ST_TileEnvelope(%(z)s, %(x)s, %(y)s, margin => 64.0 / 4096)
      AND {where}
    ORDER BY p.latest_aadf DESC NULLS LAST
) t WHERE t.geom IS NOT NULL
"""

# Road the flow applies to. With OS Open Roads loaded (PLAN-008 T2), real geometry:
# 'major' (DfT link cut from OS roads) and 'minor' (a stretch grown from the count point);
# otherwise, and for the few major links not matched, DfT's straight MRDB line ('schematic').
_SCHEMATIC = """
    SELECT p.count_point_id AS id, p.latest_aadf AS aadf, p.quality, 'schematic' AS kind,
           ST_AsMVTGeom(p.link_3857, ST_TileEnvelope(%(z)s, %(x)s, %(y)s), 4096, 64, true) AS geom
    FROM geo.traffic_count_point p
    WHERE p.link_3857 && ST_TileEnvelope(%(z)s, %(x)s, %(y)s) AND p.quality < 3
"""

_STRETCHES = """
    SELECT s.count_point_id AS id, p.latest_aadf AS aadf, p.quality, s.method AS kind,
           ST_AsMVTGeom(ST_Simplify(s.geom_3857, %(px)s), ST_TileEnvelope(%(z)s, %(x)s, %(y)s),
                        4096, 64, true) AS geom
    FROM geo.traffic_stretch s JOIN geo.traffic_count_point p USING (count_point_id)
    WHERE s.geom_3857 && ST_TileEnvelope(%(z)s, %(x)s, %(y)s)
      AND (s.method = 'major' OR %(z)s >= %(minor_zoom)s)
"""

_UNMATCHED = """
      AND NOT EXISTS (SELECT 1 FROM geo.traffic_stretch s WHERE s.count_point_id = p.count_point_id)
"""


def stretches_available(conn: psycopg.Connection) -> bool:
    return conn.execute("SELECT to_regclass('geo.traffic_stretch') IS NOT NULL AS ok").fetchone()[
        "ok"
    ]


def links_query(with_stretches: bool) -> str:
    rows = _STRETCHES + " UNION ALL " + _SCHEMATIC + _UNMATCHED if with_stretches else _SCHEMATIC
    return (
        f"SELECT ST_AsMVT(t, 'traffic_links', 4096, 'geom') FROM ({rows}) t "
        "WHERE t.geom IS NOT NULL"
    )


@router.get("/traffic/tiles/{z}/{x}/{y}.mvt")
def traffic_tile(
    conn: Conn,
    z: Annotated[int, Path(ge=0, le=22)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
) -> Response:
    if x >= 2**z or y >= 2**z:
        raise RequestValidationError([{"loc": ("path", "x/y"), "msg": "outside tile grid"}])
    tile = {"z": z, "x": x, "y": y}
    body = bytes(
        conn.execute(sql.SQL(_POINTS).format(where=sql.SQL(point_filter(z))), tile).fetchone()[
            "st_asmvt"
        ]
    )
    if z >= LINK_ZOOM:
        query = links_query(stretches_available(conn))
        params = tile | {"minor_zoom": MINOR_LINK_ZOOM, "px": WEB_MERCATOR_WIDTH / 2**z / 4096}
        body += bytes(conn.execute(query, params).fetchone()["st_asmvt"])
    return Response(
        content=body,
        media_type=MVT_MEDIA_TYPE,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/traffic/points/{count_point_id}")
def traffic_point(conn: Conn, flt: Flt, count_point_id: Annotated[int, Path(ge=0)]) -> dict:
    point = conn.execute(
        """SELECT count_point_id AS id, road_name, road_category, road_type,
                  start_junction, end_junction, local_authority_name, region_name,
                  link_length_km, link_year, first_year, latest_year, last_counted_year,
                  quality, latest_aadf, latest_hgv_pct, latest_cycles,
                  ST_X(ST_Transform(geom_bng, 4326)) AS lon,
                  ST_Y(ST_Transform(geom_bng, 4326)) AS lat,
                  ST_AsGeoJSON(ST_Transform(link_bng, 4326), 6)::json AS link
           FROM geo.traffic_count_point WHERE count_point_id = %s""",
        (count_point_id,),
    ).fetchone()
    if point is None:
        raise NotFound(f"no count point {count_point_id}")
    series = conn.execute(
        sql.SQL(
            """SELECT year, estimation_method AS method,
                      estimation_method_detailed AS method_detailed, {cols}
               FROM geo.traffic_aadf WHERE count_point_id = %s ORDER BY year"""
        ).format(cols=sql.SQL(", ").join(map(sql.Identifier, VEHICLE_FIELDS))),
        (count_point_id,),
    ).fetchall()
    stretch = _stretch(conn, count_point_id)
    length_m = stretch["length_m"] if stretch else None
    return ok(
        point
        | {
            "stretch": stretch,
            "collisions": link_collisions(conn, flt, count_point_id, length_m),
            "safety": safety_for(conn, "link", str(count_point_id)),
            "junctions": junctions_on_road(conn, count_point_id),
            "road_category_label": ROAD_CATEGORY.get(point["road_category"] or ""),
            "series": series,
            "dft_url": DFT_COUNT_POINT_URL.format(id=count_point_id),
        }
    )


def _stretch(conn: psycopg.Connection, count_point_id: int) -> dict | None:
    """The OS roads this count applies to (PLAN-008 T2), if the network is loaded."""
    if not stretches_available(conn):
        return None
    return conn.execute(
        """SELECT method, length_m, links, name, snap_m,
                  ST_AsGeoJSON(ST_Transform(geom_bng, 4326), 6)::json AS geometry
           FROM geo.traffic_stretch WHERE count_point_id = %s""",
        (count_point_id,),
    ).fetchone()


def _data_year(conn: psycopg.Connection) -> int | None:
    return conn.execute("SELECT max(latest_year) AS y FROM geo.traffic_count_point").fetchone()["y"]


def _area_where(flt: Filter) -> tuple[sql.Composable, dict]:
    """Count points inside the filter's area (alias c, as the collision filters use)."""
    if flt.area is None:
        return sql.SQL("TRUE"), {}
    return area_condition(flt.area)


_COUNTS = """
SELECT count(*) FILTER (WHERE c.road_type = 'Major' AND c.quality < 3) AS major,
       count(*) FILTER (WHERE c.road_type = 'Minor' AND c.quality < 3) AS minor,
       count(*) FILTER (WHERE c.quality = 3) AS historic
FROM geo.traffic_count_point c WHERE {where}
"""

_TOP = """
SELECT c.count_point_id AS id, c.road_name, c.road_category, c.start_junction,
       c.end_junction, c.latest_aadf AS aadf, c.latest_hgv_pct AS hgv_pct, c.quality,
       c.latest_year
FROM geo.traffic_count_point c
WHERE {where} AND c.quality < 3 AND c.latest_aadf IS NOT NULL
ORDER BY c.latest_aadf DESC LIMIT %(top)s
"""

# Major-road vehicle-km by year inside the area: each DfT link counts for the share of its
# line (MRDB) inside the area, so a link mostly outside a small drawn area doesn't count in
# full (FU-047 #6). A link without a line counts in full when its count point is inside.
# Lengths are that year's where DfT gives them (FU-047 #8).
_MAJOR_TREND = """
WITH area AS (SELECT {area} AS g),
links AS (
    SELECT c.count_point_id,
           CASE WHEN (SELECT g FROM area) IS NULL THEN 1.0
                WHEN c.link_bng IS NOT NULL AND ST_Length(c.link_bng) > 0
                    THEN ST_Length(ST_Intersection(c.link_bng, (SELECT g FROM area)))
                         / ST_Length(c.link_bng)
                WHEN ST_Intersects(c.geom_bng, (SELECT g FROM area)) THEN 1.0
                ELSE 0.0 END AS share,
           c.link_length_km
    FROM geo.traffic_count_point c
    WHERE c.road_type = 'Major'
      AND ((SELECT g FROM area) IS NULL
           OR ST_Intersects(coalesce(c.link_bng, c.geom_bng), (SELECT g FROM area)))
)
SELECT a.year,
       round(sum(a.all_motor_vehicles * coalesce(a.link_length_km, l.link_length_km)
                 * l.share * 365))::float AS vehicle_km,
       count(*) AS links,
       round(100.0 * avg((a.estimation_method = 'Counted')::int), 1)::float AS counted_pct
FROM links l
JOIN geo.traffic_aadf a USING (count_point_id)
WHERE l.share > 0 AND coalesce(a.link_length_km, l.link_length_km) > 0 {years}
GROUP BY a.year ORDER BY a.year
"""


def major_vehicle_km(
    conn: psycopg.Connection, area: Area | None, years: tuple[int, int] | None = None
) -> list[dict]:
    """Major-road vehicle-km by year inside the area (all of GB without one)."""
    geom, params = area_geometry(area) if area is not None else (sql.SQL("NULL::geometry"), {})
    years_sql = sql.SQL("AND a.year BETWEEN %(y0)s AND %(y1)s" if years else "")
    if years:
        params = params | {"y0": years[0], "y1": years[1]}
    query = sql.SQL(_MAJOR_TREND).format(area=geom, years=years_sql)
    return conn.execute(query, params).fetchall()


# ONS recoded these authorities in 2023; DfT's traffic tables still use the old codes.
LA_CODE_ALIASES = {
    "E08000038": "E08000016",  # Barnsley
    "E08000039": "E08000019",  # Sheffield
}


def _authority_series(conn: psycopg.Connection, flt: Filter) -> dict | None:
    """DfT's all-roads traffic for a highway authority (only that area type matches)."""
    area = flt.area
    if not isinstance(area, AuthorityArea) or area.boundary_type != "highway_authority":
        return None
    rows = conn.execute(
        """SELECT local_authority_name AS name, year, vehicle_miles, road_length_km
           FROM geo.traffic_la WHERE local_authority_code = %s ORDER BY year""",
        (LA_CODE_ALIASES.get(area.code, area.code),),
    ).fetchall()
    if not rows:
        return None
    return {
        "code": area.code,
        "name": rows[-1]["name"],
        "series": [{k: r[k] for k in ("year", "vehicle_miles", "road_length_km")} for r in rows],
    }


@router.get("/traffic/summary")
def traffic_summary(conn: Conn, flt: Flt) -> dict:
    where, params = _area_where(flt)
    counts = conn.execute(sql.SQL(_COUNTS).format(where=where), params).fetchone()
    top = conn.execute(sql.SQL(_TOP).format(where=where), params | {"top": TOP_POINTS}).fetchall()
    trend = major_vehicle_km(conn, flt.area)
    return ok(
        {
            "data_year": _data_year(conn),
            "has_area": flt.area is not None,
            "points": counts,
            "top": top,
            "major_trend": trend,
            "authority": _authority_series(conn, flt),
        }
    )
