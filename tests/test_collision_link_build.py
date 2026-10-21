"""Collisions matched to fixture OS links (PLAN-008 T3b), and the count point card's rates."""

import pytest

from stats19.api.link_collisions import link_rate
from stats19.reference.collision_link_build import match_collision_links

from .test_junction_build import loaded  # noqa: F401  (fixture)
from .test_reference_load import client  # noqa: F401  (fixture)

COLLISIONS = [
    # index, years before latest, class, number, road type, x, y
    ("ON-A30", 0, 3, 30, 6, 291452, 92246),  # 4 m off A30-1, mid-link
    ("MILL-LANE", 0, 6, 0, 6, 292450, 92803),  # Mill Lane (M1), unnumbered both sides
    ("FIELD", 0, 3, 30, 6, 291450, 92600),  # 300 m from any road
    ("OLD", 12, 3, 30, 6, 291452, 92246),  # before the matching window
]


def test_link_rate_per_100m_vehicle_km():
    # 2 km at 10,000 a day for 5 years = 36.5 M vehicle-km; 3 collisions -> 8.22
    assert link_rate(3, 2.0, 10_000, 5) == 8.22
    assert link_rate(3, 0, 10_000, 5) is None


@pytest.mark.integration
def test_collisions_match_the_best_scoring_link(loaded):  # noqa: F811
    loaded.execute("CREATE SCHEMA IF NOT EXISTS core")
    loaded.execute(
        """CREATE TABLE core.collision (collision_index text PRIMARY KEY, collision_year smallint,
               first_road_class smallint, first_road_number integer, road_type smallint,
               geom_bng geometry(Point, 27700))"""
    )
    for index, ago, cls, number, road_type, x, y in COLLISIONS:
        loaded.execute(
            "INSERT INTO core.collision VALUES (%s, 2025 - %s, %s, %s, %s,"
            " ST_SetSRID(ST_MakePoint(%s, %s), 27700))",
            (index, ago, cls, number, road_type, x, y),
        )
    loaded.commit()

    match_collision_links(loaded)

    got = loaded.execute(
        """SELECT collision_index, link_id, round(frac::numeric, 1), round(dist_m), score >= 100
           FROM geo.collision_link ORDER BY 1"""
    ).fetchall()
    assert got == [("MILL-LANE", "M1", 0.5, 3, True), ("ON-A30", "A30-1", 0.5, 4, True)]
    detail = loaded.execute(
        "SELECT detail FROM geo.reference_refresh WHERE dataset = 'collision_links'"
    ).fetchone()[0]
    assert detail == "last 10 years: 2 of 3 matched, 2 scoring 100+"
