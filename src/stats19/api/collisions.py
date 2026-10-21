"""/api/collisions/{collision_index}: one collision, decoded, with vehicles and casualties."""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Path

from stats19.api.deps import get_conn
from stats19.api.envelope import NotFound, ok

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]

# Geometry columns are binary; expose lon/lat instead.
_DROP = "- 'geom_bng' - 'geom_wgs84' - 'geom_3857'"


def _authority_names(
    conn: psycopg.Connection, highway: str | None, district: str | None
) -> dict[str, str | None]:
    """Current boundary names for the collision's highway authority and district codes."""
    rows = conn.execute(
        """SELECT boundary_type, name FROM geo.boundary
           WHERE (boundary_type = 'highway_authority' AND code = %s)
              OR (boundary_type = 'district' AND code = %s)""",
        (highway, district),
    ).fetchall()
    names = {r["boundary_type"]: r["name"] for r in rows}
    return {
        "highway_authority_name": names.get("highway_authority"),
        "district_name": names.get("district"),
    }


@router.get("/collisions/{collision_index}")
def get_collision(
    conn: Conn,
    collision_index: Annotated[str, Path(pattern=r"^[0-9A-Z]{4,20}$")],
) -> dict:
    collision = conn.execute(
        f"""SELECT (to_jsonb(d) {_DROP})
                   || jsonb_build_object('lon', ST_X(d.geom_wgs84), 'lat', ST_Y(d.geom_wgs84))
                   AS row
            FROM mart.collision_decoded d WHERE d.collision_index = %s""",
        (collision_index,),
    ).fetchone()
    if collision is None:
        raise NotFound(f"no collision {collision_index}")
    row = collision["row"]
    row |= _authority_names(
        conn,
        highway=row.get("local_authority_highway_current") or row.get("local_authority_highway"),
        district=row.get("local_authority_ons_district"),
    )
    vehicles = conn.execute(
        """SELECT to_jsonb(v) AS row FROM mart.vehicle_decoded v
           WHERE v.collision_index = %s ORDER BY v.vehicle_reference""",
        (collision_index,),
    ).fetchall()
    casualties = conn.execute(
        """SELECT to_jsonb(k) AS row FROM mart.casualty_decoded k
           WHERE k.collision_index = %s ORDER BY k.casualty_reference, k.casualty_seq""",
        (collision_index,),
    ).fetchall()
    return ok(
        {
            "collision": row,
            "vehicles": [r["row"] for r in vehicles],
            "casualties": [r["row"] for r in casualties],
        }
    )
