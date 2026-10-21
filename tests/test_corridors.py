"""The corridor view (PLAN-009 V2): ordering links along a road, route totals, the API."""

import json
import random

import pytest

from stats19.api.corridor_order import GAP_KM, Link, chain, fraction_along, link_ends
from stats19.api.corridors import band_of, summarise


def keys(placed):
    return [p.key for p in placed]


def test_link_ends_are_the_two_part_ends_furthest_apart():
    # a dual carriageway: two parts whose ends sit 30 m apart
    ends = [(0, 0), (1000, 30), (0, 30), (1000, 0)]

    a, b = link_ends(ends)

    assert {a[0], b[0]} == {0, 1000}


def test_chain_orders_shuffled_links_west_to_east():
    links = [Link(str(i), (i * 1000.0, 0.0), ((i + 1) * 1000.0, 0.0), 1.0) for i in range(8)]
    shuffled = random.Random(4).sample(links, len(links))
    # some links digitised the other way
    shuffled = [Link(x.key, x.b, x.a, x.length_km) if int(x.key) % 3 == 0 else x for x in shuffled]

    placed = chain(shuffled)

    assert keys(placed) == [str(i) for i in range(8)]
    assert all(p.start[0] < p.end[0] for p in placed)
    assert all(p.gap_before_km == 0 for p in placed)


def test_a_north_south_road_runs_south_to_north():
    links = [Link(str(i), (0.0, (5 - i) * 1000.0), (0.0, (4 - i) * 1000.0), 1.0) for i in range(5)]

    placed = chain(links)

    assert keys(placed) == ["4", "3", "2", "1", "0"]
    assert placed[0].start[1] < placed[-1].end[1]


def test_a_section_outside_the_area_is_a_gap():
    # the road leaves the area for 6.5 km (the A30 on the M5 between junctions 31 and 29)
    links = [
        Link("w1", (0.0, 0.0), (1000.0, 0.0), 1.0),
        Link("w2", (1000.0, 0.0), (2000.0, 0.0), 1.0),
        Link("e1", (8500.0, 0.0), (9500.0, 0.0), 1.0),
        Link("e2", (9500.0, 0.0), (10500.0, 0.0), 1.0),
    ]

    placed = chain(links)

    assert keys(placed) == ["w1", "w2", "e1", "e2"]
    assert [p.gap_before_km for p in placed] == [0, 0, pytest.approx(6.5), 0]


def test_dual_carriageway_ends_a_few_metres_apart_are_not_a_gap():
    links = [
        Link("a", (0.0, 0.0), (1000.0, 0.0), 1.0),
        Link("b", (1000.0, 40.0), (2000.0, 40.0), 1.0),
    ]

    assert [p.gap_before_km for p in chain(links)] == [0, 0]
    assert GAP_KM * 1000 > 40


def test_a_skipped_spur_is_moved_back_beside_its_neighbours():
    # nearest-neighbour from the west end takes the main line first and would reach the
    # short piece "m" (between 2 and 3, offset) last with a long jump back
    links = [Link(str(i), (i * 1000.0, 0.0), ((i + 1) * 1000.0, 0.0), 1.0) for i in range(6)]
    links.append(Link("m", (2900.0, 250.0), (3100.0, 250.0), 0.2))

    placed = chain(links)

    assert keys(placed).index("m") in (3, 4)
    assert sum(p.gap_before_km for p in placed) < 2


def test_one_link_is_a_route():
    assert keys(chain([Link("x", (5.0, 5.0), (0.0, 0.0), 0.1)])) == ["x"]
    assert chain([]) == []


def test_fraction_along_a_link():
    assert fraction_along((0, 0), (1000, 0), (250, 10)) == pytest.approx(0.25, abs=0.01)
    assert fraction_along((0, 0), (0, 0), (0, 0)) == 0.5


@pytest.mark.parametrize(
    ("excess", "rank", "size", "band"),
    [
        (5.0, 1, 200, 3),
        (2.0, 10, 200, 2),
        (1.0, 40, 200, 1),
        (-1.0, 40, 200, 0),  # a high rank with no excess isn't "worse"
        (0.0, 100, 200, 0),
        (-2.0, 190, 200, -1),
        (None, 1, 200, None),
    ],
)
def test_band_matches_the_risk_layer(excess, rank, size, band):
    assert band_of(excess, rank, size) == band


def test_route_totals_add_scored_links():
    links = [
        # 10,000 AADF over 2 km for 5 years = 0.365 x 100M vkm
        {
            "observed": 4,
            "ksi": 1,
            "excess": 1.5,
            "value_per_year": 30_000,
            "band": 2,
            "flow": 10_000,
            "length_km": 2.0,
        },
        {
            "observed": 2,
            "ksi": 0,
            "excess": -0.5,
            "value_per_year": -10_000,
            "band": 0,
            "flow": 10_000,
            "length_km": 1.0,
        },
        {"observed": None, "length_km": 0.5},  # traced but not scored
    ]

    t = summarise(links)

    assert (t["links"], t["scored"], t["length_km"], t["observed"], t["ksi"]) == (3, 2, 3.5, 6, 1)
    assert t["vkm_100m"] == pytest.approx(10_000 * 3 * 365 * 5 / 1e8, abs=1e-3)
    assert t["per_100m_vkm"] == pytest.approx(6 / (10_000 * 3 * 365 * 5 / 1e8), abs=0.1)
    assert (t["excess"], t["value_per_year"], t["worst_5pct"]) == (1.0, 20_000, 1)
    assert t["excess_worse"] == 1.5  # the better link's -0.5 doesn't offset it


def test_route_totals_with_nothing_scored():
    t = summarise([{"observed": None, "length_km": 1.0}])

    assert (t["per_100m_vkm"], t["excess"], t["value_per_year"]) == (None, None, None)


# ------------------------------------------------------------------ API


@pytest.mark.integration
def test_routes_rank_and_corridor(api, db_conn):
    from stats19.reference.collision_link_build import match_collision_links
    from stats19.reference.safety_build import build_safety

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
    build_safety(db_conn)
    # give the link a model so it has an excess and a value
    db_conn.execute(
        """UPDATE geo.safety_unit SET predicted = 0.5, eb = 0.8, excess = 0.3, excess_rank = 1,
                  group_size = 50 WHERE unit_type = 'link' AND unit_id = '1001'"""
    )
    db_conn.execute(
        "INSERT INTO geo.safety_model VALUES ('link', 'principal_a', 50, 0, '{}', 0.5, 1, 100, 10, 1)"
    )
    db_conn.commit()

    ranked = api.get("/api/routes").json()["data"]

    assert ranked["available"] is True and ranked["years"] == 5
    a30 = next(r for r in ranked["routes"] if r["road"] == "A30")
    assert (a30["links"], a30["observed"], a30["excess"], a30["worst_5pct"]) == (1, 1, 0.3, 1)
    assert a30["value_per_year"] > 0
    # 2.059 km is above the 2 km floor for ranking by rate
    worse = api.get("/api/routes", params={"sort": "worse"}).json()["data"]
    assert worse["sort"] == "worse" and worse["routes"][0]["excess_worse"] == 0.3
    by_rate = api.get("/api/routes", params={"sort": "rate"}).json()["data"]
    assert "A30" in [r["road"] for r in by_rate["routes"]]

    devon = {
        "area": {"type": "authority", "boundary_type": "highway_authority", "code": "E10000008"}
    }
    d = api.get("/api/routes/A30", params={"f": json.dumps(devon)}).json()["data"]

    assert d["road"] == "A30" and d["totals"]["observed"] == 1
    [link] = d["links"]
    assert (link["count_point_id"], link["band"], link["gap_before_km"]) == (
        1001,
        2,
        0,
    )  # rank 1 of 50: the worst 5%
    assert link["geometry"]["type"] in ("LineString", "MultiLineString")
    assert "excess_rank" not in link and "observed_total" not in link
    assert all(j["link"] == 0 and 0 <= j["frac"] <= 1 for j in d["junctions"])

    empty = api.get("/api/routes/A9999").json()["data"]
    assert empty["links"] == [] and empty["totals"]["links"] == 0


@pytest.mark.integration
def test_route_names_are_validated(api):
    assert api.get("/api/routes/DROP").status_code == 422
    assert api.get("/api/routes/B3212").status_code == 422
    assert api.get("/api/routes/A1(M)").status_code == 200
