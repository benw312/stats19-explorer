"""The sun and headings at collisions, built in the database (PLAN-012 C1)."""

import pytest

from stats19 import db
from stats19.reference.context_build import build_context

# Near Coventry (52.5° N, 1.5° W), on the March equinox of 2024: the sun rose at about
# 06:05 GMT, almost due east. At 06:30 it's a few degrees up, a little south of east.
LON, LAT = -1.5, 52.5
CORE = [
    "CREATE SCHEMA IF NOT EXISTS core",
    """CREATE TABLE core.collision (
           collision_index text PRIMARY KEY, collision_year smallint, collision_date date,
           collision_time time, junction_detail_historic smallint, junction_detail smallint,
           road_type smallint, junction_control smallint,
           geom_wgs84 geometry(Point, 4326), geom_bng geometry(Point, 27700))""",
    """CREATE TABLE core.vehicle (collision_index text, vehicle_reference smallint,
           vehicle_direction_from smallint, vehicle_direction_to smallint)""",
    """CREATE TABLE geo.road_link (id text PRIMARY KEY, geom_bng geometry(LineString, 27700))""",
    """CREATE TABLE geo.collision_link (collision_index text PRIMARY KEY, link_id text,
           frac double precision)""",
]


def collision(conn, index, day, clock, *, junction=False):
    conn.execute(
        """INSERT INTO core.collision VALUES (%s, extract(year FROM %s::date), %s, %s,
               -1, %s, 6, -1, ST_SetSRID(ST_MakePoint(%s, %s), 4326),
               ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), 27700))""",
        (index, day, day, clock, 13 if junction else 0, LON, LAT, LON, LAT),
    )


@pytest.fixture
def built(db_conn):
    db.migrate(db_conn)
    for statement in CORE:
        db_conn.execute(statement)
    collision(db_conn, "DAWN", "2024-03-20", "06:30")
    collision(db_conn, "NIGHT", "2024-03-20", "23:00")
    collision(db_conn, "OLD", "1985-03-20", "06:30")  # before the link matches: compass only
    vehicles = [
        ("DAWN", 1, 7, 3),  # west to east, into the sunrise
        ("DAWN", 2, 3, 7),  # east to west, sun behind
        ("DAWN", 3, 0, 0),  # parked: no heading
        ("NIGHT", 1, 7, 3),
        ("OLD", 1, 7, 3),
    ]
    for v in vehicles:
        db_conn.execute("INSERT INTO core.vehicle VALUES (%s, %s, %s, %s)", v)
    # a link through the collisions, digitised towards 80° (east, a little north)
    db_conn.execute(
        """INSERT INTO geo.road_link
           SELECT 'L1', ST_MakeLine(
               ST_Translate(p, -500 * sin(radians(80)), -500 * cos(radians(80))),
               ST_Translate(p, 500 * sin(radians(80)), 500 * cos(radians(80))))
           FROM (SELECT geom_bng AS p FROM core.collision WHERE collision_index = 'DAWN') c"""
    )
    db_conn.execute(
        "INSERT INTO geo.collision_link VALUES ('DAWN', 'L1', 0.5), ('NIGHT', 'L1', 0.5)"
    )
    db_conn.commit()
    build_context(db_conn)
    return db_conn


@pytest.mark.integration
def test_the_sun_at_each_collision(built):
    rows = dict(
        built.execute(
            "SELECT collision_index, sun_elevation_deg FROM geo.collision_context"
        ).fetchall()
    )
    assert 2 < rows["DAWN"] < 6 and rows["NIGHT"] < -20
    azimuth = built.execute(
        "SELECT sun_azimuth_deg FROM geo.collision_context WHERE collision_index = 'DAWN'"
    ).fetchone()[0]
    assert 90 < azimuth < 97


@pytest.mark.integration
def test_headings_and_bands_for_moving_vehicles(built):
    rows = {
        (r[0], r[1]): r[2:]
        for r in built.execute(
            """SELECT collision_index, vehicle_reference, round(heading_deg::numeric),
                      heading_source, sun_band FROM geo.vehicle_context"""
        )
    }
    # grid north is about 1° west of true north here, so the link's 80° (grid) is ~81° true
    dawn_east = rows[("DAWN", 1)]
    assert 80 <= dawn_east[0] <= 82 and dawn_east[1:] == ("link", "low_ahead")
    dawn_west = rows[("DAWN", 2)]
    assert 260 <= dawn_west[0] <= 262 and dawn_west[1:] == ("link", "low_behind")
    assert ("DAWN", 3) not in rows  # parked
    assert rows[("NIGHT", 1)][2] == "dark"
    assert rows[("OLD", 1)] == (90, "compass", "low_ahead")
    detail = built.execute(
        "SELECT detail FROM geo.reference_refresh WHERE dataset = 'context'"
    ).fetchone()[0]
    assert detail.startswith("3 collisions") and "4 vehicles with a heading, 3 of them" in detail
