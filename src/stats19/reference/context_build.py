"""The sun at every collision, and each moving vehicle's heading and sun band (PLAN-012 C1).

Two tables, rebuilt by the ``context`` derived step after the collision links:

- ``geo.collision_context``: per collision with a time and a place, the sun's elevation
  and azimuth (stats19.reference.sun). "Dark" and "sun up" need nothing more.
- ``geo.vehicle_context``: per vehicle with a heading (parked, unknown and missing
  directions have none), the heading, where it came from (``link`` or ``compass``), the
  sun's bearing relative to it (negative: to the left) and the sun band.

They're in ``geo`` with the other derived tables, not in ``mart`` as PLAN-012 §4 first
said: the mart schema is replaced whole on every load, which would drop them.

A collision matched to an OS link (the last ``COLLISION_YEARS``; FU-037) uses the link's
bearing over 20 m either side of the collision, as an azimuth from true north on the
ellipsoid (OS grid north differs from true north by up to ~4° across GB). Earlier years
use the police compass alone.
"""

from __future__ import annotations

import logging

import numpy as np
import psycopg

from stats19.reference import sun
from stats19.reference.junction_build import JUNCTION_COLLISION
from stats19.reference.swap import swap_tables, tables_exist

log = logging.getLogger(__name__)

BEARING_HALF_SPAN_M = 20.0  # the link's bearing from 20 m before the collision to 20 m after

_DDL = (
    "DROP TABLE IF EXISTS geo.collision_context__new, geo.vehicle_context__new",
    """CREATE TABLE geo.collision_context__new (
           collision_index text NOT NULL, sun_elevation_deg real NOT NULL,
           sun_azimuth_deg real NOT NULL)""",
    """CREATE TABLE geo.vehicle_context__new (
           collision_index text NOT NULL, vehicle_reference smallint NOT NULL,
           heading_deg real NOT NULL, heading_source text NOT NULL,
           sun_relative_deg real, sun_band text NOT NULL)""",
)

_BEARINGS = f"""
CREATE TEMP TABLE link_bearing ON COMMIT DROP AS
SELECT cl.collision_index,
       degrees(ST_Azimuth(
           ST_Transform(ST_LineInterpolatePoint(l.geom_bng, greatest(cl.frac - s.f, 0)),
                        4326)::geography,
           ST_Transform(ST_LineInterpolatePoint(l.geom_bng, least(cl.frac + s.f, 1)),
                        4326)::geography)) AS bearing
FROM geo.collision_link cl
JOIN geo.road_link l ON l.id = cl.link_id
CROSS JOIN LATERAL (
    SELECT {BEARING_HALF_SPAN_M} / nullif(ST_Length(l.geom_bng), 0) AS f) s
WHERE s.f IS NOT NULL
"""

_ROWS = """
SELECT c.collision_index, v.vehicle_reference, c.collision_date,
       extract(epoch FROM c.collision_time)::int AS clock,
       ST_Y(c.geom_wgs84) AS lat, ST_X(c.geom_wgs84) AS lon,
       v.vehicle_direction_from, v.vehicle_direction_to,
       {junction} AS at_junction, {bearing} AS bearing
FROM core.collision c
LEFT JOIN core.vehicle v ON v.collision_index = c.collision_index
{join}
WHERE c.collision_year = %(year)s
  AND c.collision_time IS NOT NULL AND c.geom_wgs84 IS NOT NULL
ORDER BY c.collision_index, v.vehicle_reference
"""


def year_context(rows: list[tuple]) -> tuple[list[tuple], list[tuple]]:
    """(collision rows, vehicle rows) for one year's query rows (``_ROWS``)."""
    if not rows:
        return [], []
    cols = list(zip(*rows, strict=True))
    index = np.array(cols[0], dtype=object)
    vehicle = np.array([-1 if v is None else v for v in cols[1]])
    days = np.array(cols[2], dtype="datetime64[D]")
    clock = np.array(cols[3], dtype="int64")
    lat = np.array(cols[4], dtype=float)
    lon = np.array(cols[5], dtype=float)
    frm = np.array([-1 if v is None else v for v in cols[6]])
    to = np.array([-1 if v is None else v for v in cols[7]])
    at_junction = np.array([bool(v) for v in cols[8]])
    bearing = np.array([np.nan if v is None else v for v in cols[9]], dtype=float)

    elevation, azimuth = sun.solar_position(sun.local_to_utc(days, clock), lat, lon)
    heading, source = sun.headings(sun.compass_heading(frm, to), bearing, at_junction)
    relative = sun.angle_diff(azimuth, heading)
    bands = sun.sun_bands(elevation, relative)

    first = np.ones(len(index), dtype=bool)
    first[1:] = index[1:] != index[:-1]
    collisions = [
        (index[i], round(float(elevation[i]), 2), round(float(azimuth[i]), 2))
        for i in np.nonzero(first)[0]
    ]
    moving = np.nonzero((vehicle >= 0) & ~np.isnan(heading))[0]
    vehicles = [
        (
            index[i],
            int(vehicle[i]),
            round(float(heading[i]), 1),
            source[i],
            round(float(relative[i]), 1),
            bands[i],
        )
        for i in moving
    ]
    return collisions, vehicles


def build_context(conn: psycopg.Connection) -> None:
    if not tables_exist(conn, "core.collision", "core.vehicle"):
        log.info("collision context skipped: needs STATS19 loaded")
        return
    span = conn.execute(
        "SELECT min(collision_year), max(collision_year) FROM core.collision"
    ).fetchone()
    if span[0] is None:
        return
    links = tables_exist(conn, "geo.collision_link", "geo.road_link")
    query = _ROWS.format(
        junction=JUNCTION_COLLISION,
        bearing="lb.bearing" if links else "NULL::float8",
        join="LEFT JOIN link_bearing lb ON lb.collision_index = c.collision_index" if links else "",
    )
    n_collisions = n_vehicles = n_link = 0
    with conn.transaction():
        for statement in _DDL:
            conn.execute(statement)
        if links:
            conn.execute(_BEARINGS)
        for year in range(span[0], span[1] + 1):
            collisions, vehicles = year_context(conn.execute(query, {"year": year}).fetchall())
            _copy(conn, "collision_context__new", collisions)
            _copy(conn, "vehicle_context__new", vehicles)
            n_collisions += len(collisions)
            n_vehicles += len(vehicles)
            n_link += sum(1 for v in vehicles if v[3] == sun.SOURCE_LINK)
            log.info("context %s: %s collisions, %s vehicles", year, len(collisions), len(vehicles))
    swap_tables(
        conn,
        "context",
        {
            "collision_context": [
                "ALTER TABLE geo.collision_context ADD PRIMARY KEY (collision_index)"
            ],
            "vehicle_context": [
                "ALTER TABLE geo.vehicle_context "
                "ADD PRIMARY KEY (collision_index, vehicle_reference)",
                "CREATE INDEX vehicle_context_band_idx ON geo.vehicle_context (sun_band) "
                "WHERE sun_band LIKE 'low%'",
            ],
        },
        "Sun position (NOAA) and vehicle headings from STATS19 and OS Open Roads",
        n_vehicles,
        f"{n_collisions:,} collisions with a time and place; {n_vehicles:,} vehicles with a "
        f"heading, {n_link:,} of them from the matched road link",
    )


def _copy(conn: psycopg.Connection, table: str, rows: list[tuple]) -> None:
    if not rows:
        return
    with conn.cursor() as cur, cur.copy(f"COPY geo.{table} FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)
