"""/api/areas: highway authority, district and police force boundaries."""

from __future__ import annotations

from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, Query

from stats19.api.deps import get_conn
from stats19.api.envelope import NotFound, ok

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
AreaType = Literal["highway_authority", "district", "police_force"]

# Display simplification tolerance in metres (BNG); analysis uses full geometry.
_SIMPLIFY_M = 25
AT_SNAP_M = 2000


@router.get("/areas")
def list_areas(conn: Conn, type: Annotated[AreaType, Query()]) -> dict:
    rows = conn.execute(
        "SELECT code, name FROM geo.boundary WHERE boundary_type = %s ORDER BY name",
        (type,),
    ).fetchall()
    return ok(rows)


@router.get("/areas/at")
def area_at(
    conn: Conn,
    lon: Annotated[float, Query(ge=-9.0, le=3.0)],
    lat: Annotated[float, Query(ge=49.0, le=61.5)],
    type: Annotated[AreaType, Query()] = "highway_authority",
) -> dict:
    """The area of this type containing a point (a site's authority, for comparisons).

    Boundaries can be clipped to the coast, so a site on a sea wall falls back to the
    nearest area within AT_SNAP_M.
    """
    row = conn.execute(
        """WITH pt AS (SELECT ST_Transform(ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326),
                                           27700) AS g)
           SELECT b.boundary_type, b.code, b.name FROM geo.boundary b, pt
           WHERE b.boundary_type = %(type)s AND ST_DWithin(b.geom_bng, pt.g, %(snap)s)
           ORDER BY ST_Distance(b.geom_bng, pt.g), b.code LIMIT 1""",
        {"lon": lon, "lat": lat, "type": type, "snap": AT_SNAP_M},
    ).fetchone()
    if row is None:
        raise NotFound(f"no {type} at {lon}, {lat}")
    return ok(row)


@router.get("/areas/{type}/{code}")
def get_area(conn: Conn, type: AreaType, code: str) -> dict:
    row = conn.execute(
        f"""SELECT code, name, vintage,
                   ST_AsGeoJSON(ST_Transform(
                       ST_SimplifyPreserveTopology(geom_bng, {_SIMPLIFY_M}), 4326), 6)::json
                       AS geometry,
                   (SELECT ARRAY[ST_XMin(b), ST_YMin(b), ST_XMax(b), ST_YMax(b)]
                    FROM (SELECT ST_Transform(geom_bng, 4326)::box2d AS b) bb) AS bbox
            FROM geo.boundary WHERE boundary_type = %s AND code = %s""",
        (type, code),
    ).fetchone()
    if row is None:
        raise NotFound(f"no {type} with code {code}")
    return ok(row)
