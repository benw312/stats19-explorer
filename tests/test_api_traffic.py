"""Traffic flow endpoints: tiles, count-point detail and area summary (PLAN-008 T1)."""

import json

import pytest

from stats19.api.traffic import links_query, point_filter

from .test_api_map import MVT, tile_for

pytestmark = pytest.mark.integration

# Fixture count points are near Exeter (lon -3.53, lat 50.72).
LON, LAT = -3.53, 50.725
DEVON = {"type": "authority", "boundary_type": "highway_authority", "code": "E10000008"}


def _tile(api, z):
    x, y = tile_for(LON, LAT, z)
    return api.get(f"/api/traffic/tiles/{z}/{x}/{y}.mvt")


def _summary(api, f=None):
    params = {"f": json.dumps(f)} if f is not None else {}
    r = api.get("/api/traffic/summary", params=params)
    assert r.status_code == 200
    return r.json()["data"]


@pytest.mark.parametrize(
    ("z", "expected"),
    [
        (5, "p.road_category IN ('TM', 'PM', 'TA') AND p.quality < 3"),
        (7, "p.road_type = 'Major' AND p.quality < 3"),
        (9, "p.quality < 3"),
        (12, "TRUE"),
    ],
)
def test_point_filter_by_zoom(z, expected):
    assert point_filter(z) == expected


def test_tile_has_points_and_links_when_zoomed_in(api):
    r = _tile(api, 12)

    assert r.status_code == 200
    assert r.headers["content-type"] == MVT
    assert b"traffic_points" in r.content
    assert b"traffic_links" in r.content


def test_tile_has_no_links_when_zoomed_out(api):
    r = _tile(api, 8)

    assert b"traffic_points" in r.content
    assert b"traffic_links" not in r.content


def test_tile_outside_grid_rejected(api):
    assert api.get("/api/traffic/tiles/3/9/0.mvt").status_code == 422


def test_point_detail(api):
    r = api.get("/api/traffic/points/1002")

    assert r.status_code == 200
    d = r.json()["data"]
    assert d["road_name"] == "A38"
    assert d["road_category_label"] == "Trunk A road"
    assert (d["quality"], d["last_counted_year"], d["latest_aadf"]) == (1, 2022, 31500)
    assert [s["year"] for s in d["series"]] == [2022, 2023, 2024, 2025]
    assert d["series"][0]["method"] == "Counted"
    assert d["link"]["type"] == "MultiLineString"
    assert d["dft_url"] == "https://roadtraffic.dft.gov.uk/count-points/1002"
    assert -3.6 < d["lon"] < -3.4


def test_minor_point_has_no_link(api):
    d = api.get("/api/traffic/points/1003").json()["data"]

    assert d["link"] is None
    assert d["road_category_label"] == "C or unclassified road"


def test_point_not_found(api):
    r = api.get("/api/traffic/points/424242")

    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_summary_without_area_covers_everything(api):
    d = _summary(api)

    assert d["data_year"] == 2025
    assert d["has_area"] is False
    assert d["points"] == {"major": 2, "minor": 1, "historic": 1}
    assert [t["id"] for t in d["top"]] == [1002, 1001, 1004]  # current points by flow
    assert d["authority"] is None
    last = d["major_trend"][-1]
    assert last["year"] == 2025
    assert last["vehicle_km"] == round((21000 * 2.0 + 31500 * 1.5) * 365)
    assert last["counted_pct"] == 50.0


def test_summary_for_highway_authority_adds_dft_series(api):
    d = _summary(api, {"area": DEVON})

    assert d["has_area"] is True
    assert d["authority"]["name"] == "Devon"
    assert [s["year"] for s in d["authority"]["series"]] == [2024, 2025]
    assert d["authority"]["series"][-1]["vehicle_miles"] == 7.0e9


def test_summary_for_district_has_no_authority_series(api):
    d = _summary(
        api, {"area": {"type": "authority", "boundary_type": "district", "code": "E07000041"}}
    )

    assert d["authority"] is None
    assert d["points"]["major"] == 2


def test_summary_for_empty_area(api):
    d = _summary(api, {"area": {"type": "radius", "lon": -1.0, "lat": 52.0, "radius_m": 500}})

    assert d["points"] == {"major": 0, "minor": 0, "historic": 0}
    assert d["top"] == [] and d["major_trend"] == []


def test_summary_maps_recoded_authority_to_dft_code(api, db_conn):
    # ONS recoded Sheffield to E08000039 in 2023; DfT still publishes it as E08000019.
    db_conn.execute(
        "INSERT INTO geo.traffic_la VALUES ('E08000019', 'Sheffield', 2025, 2000, 1e9, 1.5e9)"
    )
    db_conn.commit()
    sheffield = {"type": "authority", "boundary_type": "highway_authority", "code": "E08000039"}

    d = _summary(api, {"area": sheffield})

    assert d["authority"]["name"] == "Sheffield"
    assert d["authority"]["series"] == [
        {"year": 2025, "vehicle_miles": 1.5e9, "road_length_km": 2000.0}
    ]


def test_major_point_has_its_os_stretch(api):
    s = api.get("/api/traffic/points/1001").json()["data"]["stretch"]

    assert (s["method"], s["length_m"], s["links"]) == ("major", 2059.0, 2)
    assert s["geometry"]["type"] == "MultiLineString"


def test_minor_point_stretch_carries_the_os_street_name(api):
    s = api.get("/api/traffic/points/1003").json()["data"]["stretch"]

    assert (s["method"], s["name"], s["length_m"]) == ("minor", "Mill Lane", 250.0)
    assert s["snap_m"] == 0.0


def test_link_tiles_draw_os_roads_by_kind(api):
    r = _tile(api, 12)

    assert b"traffic_links" in r.content
    assert b"major" in r.content and b"minor" in r.content


def test_minor_stretches_wait_for_street_zoom(api):
    r = _tile(api, 10)

    assert b"major" in r.content
    assert b"minor" not in r.content


def test_links_query_falls_back_to_dft_lines_without_os_roads():
    assert "traffic_stretch" not in links_query(False)
    assert "schematic" in links_query(False)
    assert "UNION ALL" in links_query(True)


def test_area_major_traffic_counts_only_the_part_of_each_link_inside(api, db_conn):
    # FU-047 #6: a 300 m circle on the A30's DfT line keeps a 600 m chord of its 2,059 m,
    # not the whole link (the A38's line is over 1 km away)
    lon, lat = db_conn.execute(
        "SELECT ST_X(g), ST_Y(g) FROM (SELECT ST_Transform(ST_SetSRID("
        "ST_MakePoint(291450, 92250), 27700), 4326) AS g) p"
    ).fetchone()
    area = {"type": "radius", "lon": lon, "lat": lat, "radius_m": 300}

    trend = {y["year"]: y for y in _summary(api, {"area": area})["major_trend"]}

    share = 600 / (1800**2 + 1000**2) ** 0.5
    assert trend[2025]["vehicle_km"] == pytest.approx(21_000 * 2.0 * 365 * share, rel=0.01)
