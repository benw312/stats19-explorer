"""The site page's supporting endpoints (PLAN-009 V3): a point's authority, overlapping
sites, and the junction and road PDFs."""

import json
import urllib.parse

import pytest

from .test_api_junctions import junction_api  # noqa: F401 - fixture
from .test_reports import captured  # noqa: F401 - fixture


@pytest.mark.integration
def test_area_at_a_point(api):
    r = api.get("/api/areas/at", params={"lon": -3.53, "lat": 50.72})

    assert r.status_code == 200
    assert r.json()["data"] == {
        "boundary_type": "highway_authority",
        "code": "E10000008",
        "name": "Devon",
    }
    # out at sea: nothing within the snap distance
    assert api.get("/api/areas/at", params={"lon": 2.9, "lat": 51.0}).status_code == 404
    assert api.get("/api/areas/at", params={"lon": 20, "lat": 50}).status_code == 422


@pytest.mark.integration
def test_road_lists_the_junctions_on_it(junction_api):  # noqa: F811
    # P3's Mill Lane arm is counted by count point 1003
    road = junction_api.get("/api/traffic/points/1003").json()["data"]

    assert [j["id"] for j in road["junctions"]] == ["P3"]
    assert road["junctions"][0]["band"] is None  # not scored without the safety build


@pytest.mark.integration
def test_sites_near_a_point(junction_api, db_conn):  # noqa: F811
    from stats19.reference.safety_build import build_safety

    build_safety(db_conn)
    near = junction_api.get(
        "/api/sites/near", params={"lon": -3.53, "lat": 50.72, "radius_m": 2000}
    ).json()["data"]

    assert near["available"] is True
    assert all(r["distance_m"] <= 2000 for r in near["roads"] + near["junctions"])
    assert all("excess_rank" not in r for r in near["roads"] + near["junctions"])
    distances = [r["distance_m"] for r in near["roads"]]
    assert distances == sorted(distances)
    too_far = {"lon": -3.53, "lat": 50.72, "radius_m": 5000}
    assert junction_api.get("/api/sites/near", params=too_far).status_code == 422


@pytest.mark.integration
def test_junction_and_road_pdfs(junction_api, captured):  # noqa: F811
    f = {"year_from": 1979, "year_to": 1980}
    r = junction_api.get(
        "/api/reports/junction/P3.pdf", params={"f": json.dumps(f), "title": "Mill Lane"}
    )

    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    url = urllib.parse.urlparse(captured[-1])
    assert url.path == "/print/junction/P3"
    assert json.loads(urllib.parse.parse_qs(url.query)["f"][0]) == f

    r = junction_api.get("/api/reports/road/1001.pdf")
    assert r.status_code == 200
    assert urllib.parse.urlparse(captured[-1]).path == "/print/road/1001"
    assert 'filename="stats19-road-1001-' in r.headers["content-disposition"]

    before = len(captured)
    assert junction_api.get("/api/reports/junction/NOPE.pdf").status_code == 404
    assert junction_api.get("/api/reports/road/999999.pdf").status_code == 404
    assert len(captured) == before


@pytest.mark.integration
def test_cluster_sites_link_the_worst_scored_site_inside_them(junction_api, db_conn):  # noqa: F811
    from stats19.api.sites import worst_within
    from stats19.reference.safety_build import build_safety

    # flows in the fixture's collision years, so road 1001 is scored
    db_conn.execute(
        "INSERT INTO geo.traffic_aadf (count_point_id, year, all_motor_vehicles)"
        " VALUES (1001, 1979, 10000), (1001, 1980, 10000)"
    )
    db_conn.commit()
    build_safety(db_conn)
    # make road 1001 the worst 1% of its group
    db_conn.execute(
        """UPDATE geo.safety_unit SET predicted = 1, eb = 4, excess = 3, excess_rank = 1,
                  group_size = 200 WHERE unit_type = 'link' AND unit_id = '1001'"""
    )
    db_conn.commit()
    lon, lat = db_conn.execute(
        """SELECT ST_X(ST_Transform(geom_bng, 4326)), ST_Y(ST_Transform(geom_bng, 4326))
           FROM geo.safety_unit WHERE unit_id = '1001'"""
    ).fetchone()

    found = worst_within(
        db_conn,
        [
            {"rank": 1, "lon": lon, "lat": lat, "radius_m": 50},
            {"rank": 2, "lon": lon + 0.05, "lat": lat, "radius_m": 50},  # ~3.5 km away
        ],
    )

    assert set(found) == {1}
    assert (found[1]["unit_type"], found[1]["unit_id"], found[1]["band"]) == ("link", "1001", 3)
    assert worst_within(db_conn, []) == {}
