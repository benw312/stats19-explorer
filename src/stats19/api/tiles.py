"""/api/tiles/collisions/{z}/{x}/{y}.mvt: filtered collision vector tiles.

Below POINT_ZOOM, collisions are aggregated into grid cells (layer 'collision_bins').
From POINT_ZOOM up, individual points are returned (layer 'collisions'), ordered so
fatal collisions draw on top.
"""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Path, Query, Response
from fastapi.exceptions import RequestValidationError
from psycopg import sql

from stats19.api import cache
from stats19.api.deps import get_conn
from stats19.api.filters import Filter, collision_relation, compile_filter, parse_filter
from stats19.marts import GRID_LEVELS, WEB_MERCATOR_WIDTH

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]

POINT_ZOOM = 11
BINS_PER_TILE = 32  # grid cells across a tile when aggregated
DENSE_BINS_PER_TILE = 128  # finer bins when a point tile would be too heavy
MAX_POINTS_PER_TILE = 15_000
MVT_MEDIA_TYPE = "application/vnd.mapbox-vector-tile"


# Repeat views (another session, a reload, the next engineer) skip the database;
# zoomed-out tiles with condition filters take ~0.8 s to aggregate live (FU-013).
TILE_CACHE = cache.BytesLRU(max_bytes=128 * 1024 * 1024)


def uses_grid(f: Filter, z: int) -> bool:
    """Zoomed-out tiles with only period/severity filters read the pre-aggregated grid."""
    simple = f.model_dump(exclude_defaults=True).keys() <= {"year_from", "year_to", "severity"}
    return simple and z <= max(GRID_LEVELS)


def grid_level(z: int) -> int:
    return min(lvl for lvl in GRID_LEVELS if lvl >= z)


_POINTS = """
SELECT ST_AsMVT(t, 'collisions', 4096, 'geom') FROM (
    SELECT c.collision_index AS id, c.collision_severity AS severity,
           c.collision_year AS year,
           ST_AsMVTGeom(c.geom_3857, ST_TileEnvelope(%(z)s, %(x)s, %(y)s), 4096, 64, true) AS geom
    FROM {rel} c
    WHERE c.geom_3857 && ST_TileEnvelope(%(z)s, %(x)s, %(y)s, margin => 64.0 / 4096)
      AND {where}
    ORDER BY c.collision_severity DESC
) t WHERE t.geom IS NOT NULL
"""

_BINS = """
SELECT ST_AsMVT(t, 'collision_bins', 4096, 'geom') FROM (
    SELECT count(*) AS n,
           count(*) FILTER (WHERE c.collision_severity = 1) AS n_fatal,
           count(*) FILTER (WHERE c.collision_severity = 2) AS n_serious,
           min(c.collision_severity) AS worst,
           ST_AsMVTGeom(ST_Centroid(ST_Collect(c.geom_3857)),
                        ST_TileEnvelope(%(z)s, %(x)s, %(y)s), 4096, 0, true) AS geom
    FROM {rel} c
    WHERE c.geom_3857 && ST_TileEnvelope(%(z)s, %(x)s, %(y)s) AND {where}
    GROUP BY ST_SnapToGrid(c.geom_3857, %(cell)s)
) t WHERE t.geom IS NOT NULL
"""


_GRID = """
SELECT ST_AsMVT(t, 'collision_bins', 4096, 'geom') FROM (
    SELECT sum(g.n) AS n,
           coalesce(sum(g.n) FILTER (WHERE g.collision_severity = 1), 0) AS n_fatal,
           coalesce(sum(g.n) FILTER (WHERE g.collision_severity = 2), 0) AS n_serious,
           min(g.collision_severity) AS worst,
           ST_AsMVTGeom(ST_SetSRID(ST_MakePoint(sum(g.sum_x) / sum(g.n), sum(g.sum_y) / sum(g.n)),
                                   3857),
                        ST_TileEnvelope(%(z)s, %(x)s, %(y)s), 4096, 0, true) AS geom
    FROM mart.collision_grid g
    WHERE g.lvl = %(lvl)s AND g.cell && ST_TileEnvelope(%(z)s, %(x)s, %(y)s)
      AND {where}
    GROUP BY ST_SnapToGrid(g.cell, %(cell)s)
) t WHERE t.geom IS NOT NULL
"""

_COUNT_CAPPED = """
SELECT count(*) AS n FROM (
    SELECT 1 FROM {rel} c
    WHERE c.geom_3857 && ST_TileEnvelope(%(z)s, %(x)s, %(y)s) AND {where}
    LIMIT %(cap)s
) s
"""


def _grid_where(f: Filter) -> tuple[sql.Composable, dict]:
    parts, params = [], {}
    if f.year_from is not None:
        parts.append(sql.SQL("g.collision_year >= %(year_from)s"))
        params["year_from"] = f.year_from
    if f.year_to is not None:
        parts.append(sql.SQL("g.collision_year <= %(year_to)s"))
        params["year_to"] = f.year_to
    if f.severity:
        parts.append(sql.SQL("g.collision_severity = ANY(%(severity)s)"))
        params["severity"] = list(f.severity)
    return (sql.SQL(" AND ").join(parts) if parts else sql.SQL("TRUE")), params


def _query_for(conn: psycopg.Connection, flt: Filter, z: int, x: int, y: int):
    tile = {"z": z, "x": x, "y": y}
    cell = WEB_MERCATOR_WIDTH / 2**z / BINS_PER_TILE
    if uses_grid(flt, z):
        where, params = _grid_where(flt)
        return sql.SQL(_GRID).format(where=where), params | tile | {
            "lvl": grid_level(z),
            "cell": cell,
        }
    where, params = compile_filter(flt)
    rel = collision_relation(flt)
    if z < POINT_ZOOM:
        return sql.SQL(_BINS).format(rel=rel, where=where), params | tile | {"cell": cell}
    n = conn.execute(
        sql.SQL(_COUNT_CAPPED).format(rel=rel, where=where),
        params | tile | {"cap": MAX_POINTS_PER_TILE + 1},
    ).fetchone()["n"]
    if n > MAX_POINTS_PER_TILE:
        dense = WEB_MERCATOR_WIDTH / 2**z / DENSE_BINS_PER_TILE
        return sql.SQL(_BINS).format(rel=rel, where=where), params | tile | {"cell": dense}
    return sql.SQL(_POINTS).format(rel=rel, where=where), params | tile


@router.get("/tiles/collisions/{z}/{x}/{y}.mvt")
def collision_tile(
    conn: Conn,
    z: Annotated[int, Path(ge=0, le=22)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
    f: Annotated[str | None, Query(max_length=20_000)] = None,
) -> Response:
    if x >= 2**z or y >= 2**z:
        raise RequestValidationError([{"loc": ("path", "x/y"), "msg": "outside tile grid"}])
    flt = parse_filter(f)
    key = f"{cache.data_load(conn)}|{z}/{x}/{y}|{flt.model_dump_json(exclude_defaults=True)}"
    body = TILE_CACHE.get(key)
    if body is None:
        query, params = _query_for(conn, flt, z, x, y)
        tile = conn.execute(query, params).fetchone()
        body = bytes(next(iter(tile.values()))) if tile else b""
        TILE_CACHE.put(key, body)
    return Response(
        content=body,
        media_type=MVT_MEDIA_TYPE,
        headers={"Cache-Control": "public, max-age=3600"},
    )
