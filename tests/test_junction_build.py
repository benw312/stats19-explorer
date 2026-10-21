"""Junctions from the fixture OS network, signals and collision matching, against PostGIS."""

import pytest

from stats19 import db
from stats19.reference.junction_build import match_junction_collisions
from stats19.reference.refresh import refresh_reference

from .test_reference_load import client  # noqa: F401  (fixture)

pytestmark = pytest.mark.integration


def _rows(conn, q, p=None):
    return conn.execute(q, p).fetchall()


@pytest.fixture
def loaded(db_conn, client, tmp_path):  # noqa: F811
    db.migrate(db_conn)
    refresh_reference(db_conn, client, tmp_path, ["road_network", "traffic", "osm_nodes"])
    return db_conn


def test_junctions_are_typed_named_and_signals_marked(loaded):
    got = _rows(
        loaded,
        """SELECT id, kind, arms, name, top_class, slip_arms, nodes, signals, signalised,
                  motorway_junction
           FROM geo.junction ORDER BY id""",
    )

    assert got == [
        ("K1", "roundabout", 4, "M5 / A377 / Station Road", "Motorway", 1, 4, 1, False, "M5 J30"),
        ("P3", "t_junction", 3, "B3212 / Mill Lane", "B Road", 0, 1, 1, True, None),
        (
            "Z2",
            "mini_roundabout",
            4,
            "Bridge Street / Church Road / Market Place",
            "Unclassified",
            0,
            1,
            0,
            False,
            None,
        ),
    ]  # not N2: the A30 slip road leaves the A30 within 60 degrees, so it's one arm


def test_arms_carry_roles_and_count_points(loaded):
    arms = _rows(
        loaded,
        """SELECT junction_id, role, coalesce(road_number, name), bearing, links, count_point_id
           FROM geo.junction_arm ORDER BY junction_id, bearing""",
    )

    assert arms == [
        ("K1", "minor", "Station Road", 0, 1, None),
        ("K1", "minor", "A377", 90, 1, None),
        ("K1", "major", "M5", 159, 1, None),
        ("K1", "minor", "A377", 270, 1, None),  # the car park access is not an arm
        ("P3", "major", "B3212", 0, 1, None),
        ("P3", "minor", "Mill Lane", 90, 1, None),
        ("P3", "minor", "Mill Lane", 270, 1, 1003),  # Mill Lane's count covers the west side
        ("Z2", "major", "Bridge Street", 0, 1, None),
        ("Z2", "minor", "Church Road", 90, 1, None),
        ("Z2", "minor", "Market Place", 180, 1, None),  # shared-use street (FU-042)
        ("Z2", "minor", "Church Road", 270, 1, None),
    ]
    members = _rows(loaded, "SELECT junction_id, count(*) FROM geo.junction_node GROUP BY 1")
    assert sorted(members) == [("K1", 4), ("P3", 1), ("Z2", 1)]


def test_osm_mini_roundabout_retypes_a_plain_junction(loaded):
    # OS sees a crossroads (arm_kind); OSM's mini-roundabout node makes it a mini
    assert loaded.execute("SELECT kind, arm_kind FROM geo.junction WHERE id = 'Z2'").fetchone() == (
        "mini_roundabout",
        "crossroads",
    )


COLLISIONS = [
    # index, years before the latest, historic detail, detail, road type, control, x, y
    ("T-JUNCTION", 0, 3, 13, 6, 4, 292650, 92810),  # 10 m from P3
    ("ROUNDABOUT-2025", 0, -1, 0, 1, -1, 295000, 95035),  # 15 m from the ring, new coding
    ("FAR", 0, 3, 13, 6, 4, 292650, 92900),  # 100 m from any junction
    ("NOT-JUNCTION", 0, 0, 0, 6, 0, 292652, 92800),  # on top of P3, not a junction collision
    ("OLD", 12, 3, 13, 6, 4, 292650, 92810),  # before the matching window
]


def test_junction_collisions_go_to_the_nearest_junction(loaded):
    loaded.execute("CREATE SCHEMA IF NOT EXISTS core")
    loaded.execute(
        """CREATE TABLE core.collision (collision_index text PRIMARY KEY, collision_year smallint,
               junction_detail_historic smallint, junction_detail smallint, road_type smallint,
               junction_control smallint, geom_bng geometry(Point, 27700))"""
    )
    for index, ago, hist, detail, road_type, control, x, y in COLLISIONS:
        loaded.execute(
            "INSERT INTO core.collision VALUES (%s, 2025 - %s, %s, %s, %s, %s,"
            " ST_SetSRID(ST_MakePoint(%s, %s), 27700))",
            (index, ago, hist, detail, road_type, control, x, y),
        )
    loaded.commit()

    match_junction_collisions(loaded)

    got = _rows(
        loaded,
        "SELECT collision_index, junction_id, round(dist_m) FROM geo.junction_collision ORDER BY 1",
    )
    assert got == [("ROUNDABOUT-2025", "K1", 15), ("T-JUNCTION", "P3", 10)]
