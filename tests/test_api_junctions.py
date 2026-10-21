"""Junction endpoints (PLAN-008 T3): tiles and the junction card, plus the flow arithmetic."""

import json

import pytest

from stats19.api.junctions import (
    class_filter,
    collision_rate,
    entering_flow,
    summarise_collisions,
)
from stats19.reference.junction_build import match_junction_collisions

from .test_api_map import MVT, tile_for


def arm(role, aadf):
    return {"role": role, "aadf": aadf}


def test_through_road_counts_once_in_full_at_a_t_junction():
    # both sides of the A38 share its count (20,000 two-way); the side road has 2,000
    flow = entering_flow([arm("major", 20_000), arm("major", 20_000), arm("minor", 2_000)])

    assert flow == {
        "entering": 21_000,
        "major": 20_000,
        "minor": 1_000,
        "uncounted_major": 0,
        "uncounted_minor": 0,
        "coverage": "all",
    }


def test_uncounted_minor_arm_still_gives_major_flow():
    flow = entering_flow([arm("major", 20_000), arm("major", 18_000), arm("minor", None)])

    assert (flow["entering"], flow["coverage"], flow["uncounted_minor"]) == (19_000, "major", 1)


def test_uncounted_major_arm_is_partial():
    assert entering_flow([arm("major", None), arm("minor", 500)])["coverage"] == "partial"


def test_collision_rate_per_million_vehicles_entering():
    # 10,000 a day for 5 years = 18.25 million vehicles; 9 collisions -> 0.493 per MVE
    assert collision_rate(9, 10_000, 5) == {"per_mve": 0.493, "mve": 18.25}
    assert collision_rate(3, 0, 5) is None


def test_summary_fills_every_year_and_counts_recorded_control():
    rows = [
        {"collision_index": "a", "year": 2023, "severity": 2, "control": 2},
        {"collision_index": "b", "year": 2025, "severity": 3, "control": 2},
        {"collision_index": "c", "year": 2025, "severity": 3, "control": -1},
    ]

    got = summarise_collisions(rows, 2023, 2025)

    assert (got["total"], got["fatal"], got["serious"], got["slight"]) == (3, 0, 1, 2)
    assert got["by_year"] == [
        {"year": 2023, "fatal": 0, "serious": 1, "slight": 0},
        {"year": 2024, "fatal": 0, "serious": 0, "slight": 0},
        {"year": 2025, "fatal": 0, "serious": 0, "slight": 2},
    ]
    assert got["recorded_control"] == {
        "authorised_person": 0,
        "signals": 2,
        "stop": 0,
        "give_way": 0,
    }


@pytest.mark.parametrize(
    ("z", "expected"),
    [
        (13, "j.top_class IN ('Motorway', 'A Road', 'B Road')"),
        (14, "j.top_class IN ('Motorway', 'A Road', 'B Road', 'Classified Unnumbered')"),
        (15, "TRUE"),
    ],
)
def test_class_filter_by_zoom(z, expected):
    assert class_filter(z) == expected


# ------------------------------------------------------------------ against the API

# The api fixture loads collisions from 1979-80, so 1980 is the latest year.
FIXTURE_COLLISIONS = [
    # index, year, severity, historic detail, detail, road type, control, x, y
    ("J1980A", 1980, 3, 3, 13, 6, 4, 292650, 92810),  # at P3
    ("J1979B", 1979, 2, 3, 13, 6, 4, 292645, 92800),  # at P3
    ("J1980C", 1980, 3, -1, 0, 1, -1, 295000, 95035),  # at the roundabout
]


@pytest.fixture
def junction_api(api, db_conn):
    for index, year, sev, hist, detail, road_type, control, x, y in FIXTURE_COLLISIONS:
        db_conn.execute(
            """INSERT INTO core.collision (collision_index, collision_year, collision_severity,
                   junction_detail_historic, junction_detail, road_type, junction_control,
                   geom_bng, geom_3857)
               VALUES (%s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 27700),
                       ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 27700), 3857))""",
            (index, year, sev, hist, detail, road_type, control, x, y, x, y),
        )
    db_conn.commit()
    match_junction_collisions(db_conn)
    return api


@pytest.mark.integration
def test_junction_card_has_arms_flows_and_collisions(junction_api):
    r = junction_api.get("/api/junctions/P3")

    assert r.status_code == 200
    data = r.json()["data"]
    assert (data["name"], data["kind_label"], data["arms"], data["signalised"]) == (
        "B3212 / Mill Lane",
        "T or Y junction",
        3,
        True,
    )
    # the matched ground, saved as a scheme's footprint: a polygon around the junction
    assert data["match_area"]["type"] == "Polygon"
    ring = data["match_area"]["coordinates"][0]
    assert min(p[0] for p in ring) < data["lon"] < max(p[0] for p in ring)
    assert min(p[1] for p in ring) < data["lat"] < max(p[1] for p in ring)
    roles = [
        (a["role"], a["road_number"] or a["name"], a["count_point_id"]) for a in data["arm_list"]
    ]
    assert sorted(roles, key=str) == sorted(
        [("major", "B3212", None), ("minor", "Mill Lane", None), ("minor", "Mill Lane", 1003)],
        key=str,
    )
    assert data["flow"]["coverage"] == "partial"  # the B3212 has no count
    assert data["rate"] is None
    c = data["collisions"]
    assert (c["total"], c["serious"], c["slight"], c["year_from"], c["year_to"]) == (
        2,
        1,
        1,
        1976,
        1980,
    )
    assert c["ids"] == ["J1980A", "J1979B"]
    assert len(c["by_year"]) == 5
    assert c["recorded_control"]["give_way"] == 2
    assert data["matching"] == {"radius_m": 25.0, "years": 10, "latest_year": 1980}


@pytest.mark.integration
def test_rate_when_the_major_road_is_counted(junction_api, db_conn):
    # pretend the B3212 carries count point 1001's flow, with no count for this period
    db_conn.execute(
        "UPDATE geo.junction_arm SET count_point_id = 1001 WHERE junction_id = 'P3' AND role = 'major'"
    )
    db_conn.commit()
    aadf = db_conn.execute(
        "SELECT latest_aadf FROM geo.traffic_count_point WHERE count_point_id = 1001"
    ).fetchone()[0]
    mill_lane = db_conn.execute(
        "SELECT latest_aadf FROM geo.traffic_count_point WHERE count_point_id = 1003"
    ).fetchone()[0]

    data = junction_api.get("/api/junctions/P3").json()["data"]

    assert data["flow"]["coverage"] == "major"  # Mill Lane east has no count
    entering = round(aadf / 2) + round(mill_lane / 2)
    assert abs(data["rate"]["entering"] - entering) <= 1
    mve = data["rate"]["entering"] * 365 * 5 / 1e6
    assert data["rate"]["per_mve"] == pytest.approx(2 / mve, rel=1e-2)


@pytest.mark.integration
def test_junction_card_follows_the_filter(junction_api):
    f = json.dumps({"year_from": 1980, "year_to": 1980, "severity": [3]})

    c = junction_api.get("/api/junctions/P3", params={"f": f}).json()["data"]["collisions"]

    assert (c["total"], c["year_from"], c["year_to"]) == (1, 1980, 1980)


@pytest.mark.integration
def test_count_point_card_counts_collisions_on_its_link(junction_api, db_conn):
    from stats19.reference.collision_link_build import match_collision_links

    db_conn.execute(
        """INSERT INTO core.collision (collision_index, collision_year, collision_severity,
               first_road_class, first_road_number, road_type, junction_control, geom_bng)
           VALUES ('LINK1980', 1980, 2, 3, 30, 6, -1,
                   ST_SetSRID(ST_MakePoint(291452, 92246), 27700))"""
    )
    db_conn.execute(
        "INSERT INTO geo.traffic_aadf (count_point_id, year, all_motor_vehicles)"
        " VALUES (1001, 1979, 10000), (1001, 1980, 10000)"
    )
    db_conn.commit()
    match_collision_links(db_conn)

    c = junction_api.get("/api/traffic/points/1001").json()["data"]["collisions"]

    assert (c["total"], c["serious"], c["at_junctions"], c["low_confidence"]) == (1, 1, 0, 0)
    assert (c["year_from"], c["year_to"], c["period_aadf"]) == (1976, 1980, 10000)
    # 1 collision / (2.059 km x 10,000 x 365 x 5 / 1e8)
    assert c["per_100m_vkm"] == pytest.approx(1 / (2.059 * 10_000 * 365 * 5 / 1e8), rel=1e-2)

    # T4: the site is scored against its peer group (too few fixture sites to fit a model)
    from stats19.reference.safety_build import build_safety

    build_safety(db_conn)
    safety = junction_api.get("/api/traffic/points/1001").json()["data"]["safety"]
    assert (safety["peer_group"], safety["observed"], safety["predicted"]) == (
        "principal_a",
        1,
        None,
    )
    assert (safety["year_from"], safety["year_to"]) == (1976, 1980)
    top = junction_api.get("/api/safety/top", params={"unit": "link"}).json()["data"]
    assert top["available"] is True and top["sites"] == []  # nothing has a model to rank by
    devon = {
        "area": {"type": "authority", "boundary_type": "highway_authority", "code": "E10000008"}
    }
    r = junction_api.get("/api/safety/top", params={"unit": "junction", "f": json.dumps(devon)})
    assert r.status_code == 200

    # B5: with a model, the card values the group's collisions at DfT prices, and the map
    # layer bands the site by where its excess ranks (rank 1 of 50: the worst 5%)
    db_conn.execute(
        """UPDATE geo.safety_unit SET predicted = 2, eb = 4, excess = 2, excess_rank = 1,
                  group_size = 50 WHERE unit_id = '1001'"""
    )
    db_conn.execute(
        """INSERT INTO geo.safety_model VALUES
           ('link', 'principal_a', 50, 0, '{}', 0.5, 1, 100, 10, 1)"""
    )
    db_conn.commit()
    prices = {
        r[0]: r[1]
        for r in db_conn.execute(
            """SELECT severity, per_collision FROM geo.value_of_prevention
               WHERE data_year = (SELECT max(data_year) FROM geo.value_of_prevention)"""
        )
    }
    safety = junction_api.get("/api/traffic/points/1001").json()["data"]["safety"]
    price = {k: prices.get(k) or 0 for k in ("Fatal", "Serious", "Slight")}
    expected = (price["Fatal"] + 9 * price["Serious"] + 90 * price["Slight"]) / 100
    assert safety["value_per_collision"] == round(expected)
    assert (safety["years"], safety["price_year"]) == (5, 2025)
    top = junction_api.get("/api/safety/top", params={"unit": "link"}).json()["data"]
    assert [s["unit_id"] for s in top["sites"]] == ["1001"]
    assert top["sites"][0]["value_per_collision"] == round(expected)
    x, y = tile_for(-3.53, 50.72, 10)
    r = junction_api.get(f"/api/safety/tiles/10/{x}/{y}.mvt")
    assert r.status_code == 200 and r.headers["content-type"] == MVT
    assert b"risk_links" in r.content


@pytest.mark.integration
def test_unknown_junction_is_404(junction_api):
    assert junction_api.get("/api/junctions/NOPE").status_code == 404
    assert junction_api.get("/api/junctions/bad;id").status_code == 422


@pytest.mark.integration
def test_junction_tiles_only_when_zoomed_in(junction_api):
    x, y = tile_for(-3.522, 50.725, 15)
    r = junction_api.get(f"/api/junctions/tiles/15/{x}/{y}.mvt")
    assert r.status_code == 200
    assert r.headers["content-type"] == MVT
    assert b"junctions" in r.content

    x, y = tile_for(-3.522, 50.725, 12)
    assert junction_api.get(f"/api/junctions/tiles/12/{x}/{y}.mvt").content == b""
