"""Cluster sites, sites CSV and site-vs-area comparison over a small clustered dataset."""

from __future__ import annotations

import csv
import io
import json
import os

import pytest

pytestmark = pytest.mark.integration

SIDWELL_STREET = (291800, 92500)  # the named road in the reference fixture


def _collision(
    index: str, x: float, y: float, severity: int, light: int = 1, year: int = 2023
) -> dict:
    return {
        "collision_index": index,
        "collision_year": str(year),
        "collision_ref_no": "0" + index,
        "date": f"15/06/{year}",
        "location_easting_osgr": str(x),
        "location_northing_osgr": str(y),
        "collision_severity": str(severity),
        "light_conditions": str(light),
        "urban_or_rural_area": "1",
        "number_of_vehicles": "1",
        "number_of_casualties": "1",
        "first_road_class": "3",
        "first_road_number": "38",
    }


SX, SY = SIDWELL_STREET
SITE_A = [  # 7 slight within ~10 m; 4 of them in the dark
    _collision(f"A{i}", SX + (i % 3) * 4, SY + (i // 3) * 4, 3, light=4 if i < 4 else 1)
    for i in range(7)
]
SITE_B = [_collision(f"B{i}", SX + 300, SY + i * 5, 2) for i in range(2)]  # 2 KSI
BACKGROUND = [_collision(f"Z{i:02d}", SX + 2000 + i * 400, SY, 3, year=2022) for i in range(20)]
COLLISIONS = SITE_A + SITE_B + BACKGROUND
VEHICLES = [{"collision_index": c["collision_index"], "vehicle_reference": "1"} for c in COLLISIONS]
CASUALTIES = [
    {"collision_index": c["collision_index"], "vehicle_reference": "1", "casualty_reference": "1"}
    for c in COLLISIONS
]


@pytest.fixture
def hot_api(db_conn, make_files, tmp_path):
    import httpx
    from fastapi.testclient import TestClient

    from stats19 import db
    from stats19.api.app import create_app
    from stats19.api.hotspots import CACHE
    from stats19.pipeline import last_success, process
    from stats19.reference.refresh import refresh_reference
    from stats19.validate import Thresholds

    from .test_reference_load import _transport

    LENIENT_2022 = Thresholds(
        max_quarantine_ratio=1.0, max_parse_failure_ratio=1.0, first_year=2022
    )
    CACHE.clear()
    db.migrate(db_conn)
    process(
        db_conn,
        make_files(COLLISIONS, VEHICLES, CASUALTIES),
        last_success(db_conn),
        thresholds=LENIENT_2022,
    )
    with httpx.Client(transport=_transport([])) as client:
        refresh_reference(db_conn, client, tmp_path)
    with TestClient(create_app(os.environ["STATS19_TEST_DATABASE_URL"])) as c:
        yield c
    CACHE.clear()


def _get(api, path: str, **params) -> dict:
    query = {k: json.dumps(v) for k, v in params.items()}
    r = api.get(path, params=query)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_hotspots_rank_sites_and_label_them(hot_api):
    d = _get(hot_api, "/api/hotspots")

    assert d["selection"] == {"collisions": 29, "located": 29}
    assert d["params"]["radius_urban_m"] == 50
    a, b = d["sites"]
    assert (a["rank"], a["collisions"], a["slight"], a["ksi"], a["score"]) == (1, 7, 7, 0, 7)
    assert a["collision_ids"] == sorted(c["collision_index"] for c in SITE_A)
    assert a["roads"] == ["A38"]
    assert a["label"] == "A38, near Sidwell Street, Exeter"
    assert a["radius_m"] == 50 and -3.6 < a["lon"] < -3.4 and 50.6 < a["lat"] < 50.8
    assert (b["rank"], b["collisions"], b["ksi"]) == (2, 2, 2)  # qualifies on KSI
    assert a["by_year"] == [{"year": 2022, "n": 0, "ksi": 0}, {"year": 2023, "n": 7, "ksi": 0}]
    # the RAS4001 fixture only has the fatal value, so slight collisions add nothing
    assert d["value_price_year"] == 2025 and a["value_of_prevention"] == 0
    # no safety model in this fixture: no site is "worse than expected"
    assert [s["worse"] for s in d["sites"]] == [None, None]


def test_hotspots_respect_filter_and_params(hot_api):
    serious_only = _get(hot_api, "/api/hotspots", f={"severity": [2]})
    strict = _get(hot_api, "/api/hotspots", p={"min_collisions": 8, "min_ksi": 3})
    wide = _get(hot_api, "/api/hotspots", p={"radius_urban_m": 500, "max_sites": 1})

    assert [s["collisions"] for s in serious_only["sites"]] == [2]
    assert strict["sites"] == []
    assert (
        len(wide["sites"]) == 1 and wide["sites"][0]["collisions"] == 9
    )  # A + B in one 500 m circle


def test_hotspots_reject_bad_params(hot_api):
    r = hot_api.get("/api/hotspots", params={"p": json.dumps({"radius_urban_m": 1})})

    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_hotspots_too_large_is_refused(hot_api, monkeypatch):
    import stats19.api.hotspots as hotspots

    monkeypatch.setattr(hotspots, "MAX_HOTSPOT_COLLISIONS", 10)
    r = hot_api.get("/api/hotspots")

    assert r.status_code == 413
    assert r.json()["error"]["code"] == "too_large"


def test_hotspots_csv(hot_api):
    r = hot_api.get("/api/hotspots.csv")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "stats19-cluster-sites.csv" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert [row["rank"] for row in rows] == ["1", "2"]
    assert rows[0]["collision_ids"].split(";") == sorted(c["collision_index"] for c in SITE_A)


def test_csv_cells_cannot_be_formulas():
    from stats19.api.hotspots import CSV_COLUMNS, sites_csv

    site = {c: 0 for c in CSV_COLUMNS} | {"label": "=HYPERLINK(1)", "collision_ids": ["A1"]}
    row = list(csv.DictReader(io.StringIO(sites_csv({"sites": [site]}))))[0]

    assert row["label"] == "'=HYPERLINK(1)"


def test_compare_flags_over_represented_indicators(hot_api):
    site = {"collision_ids": [c["collision_index"] for c in SITE_A]}
    d = _get(hot_api, "/api/compare", f=site, base={})

    assert (d["collisions"], d["base_collisions"]) == (7, 29)
    by_key = {i["key"]: i for i in d["indicators"]}
    dark = by_key["dark"]
    assert (dark["n"], dark["of"], dark["base_n"], dark["base_of"]) == (4, 7, 4, 29)
    assert dark["notable"] and dark["p"] < 0.05
    assert dark["ratio"] == pytest.approx((4 / 7) / (4 / 29))
    assert not by_key["ksi"]["notable"]  # none at the site
    assert {"group", "label", "share", "base_share"} <= set(dark)


def test_compare_too_large_selection_is_refused(hot_api, monkeypatch):
    import stats19.api.compare as compare

    monkeypatch.setattr(compare, "MAX_COMPARE_SELECTION", 3)
    r = hot_api.get("/api/compare")

    assert r.status_code == 413


def test_site_filter_works_with_summary_and_describe(hot_api):
    site = {"collision_ids": [c["collision_index"] for c in SITE_B]}

    summary = _get(hot_api, "/api/summary", f=site)
    lines = _get(hot_api, "/api/describe", f=site)

    assert summary["totals"]["collisions"] == 2 and summary["totals"]["ksi"] == 2
    assert "Collisions: 2 selected individually" in lines


@pytest.fixture
def captured(monkeypatch):
    import stats19.api.report_routes as routes

    calls: list[tuple[str, float]] = []

    def fake_render(url: str, timeout_s: float = 90) -> bytes:
        calls.append((url, timeout_s))
        return b"%PDF-1.7 fake"

    monkeypatch.setattr(routes, "render_pdf", fake_render)
    return calls


def test_site_pack_renders_print_page(hot_api, captured):
    import urllib.parse

    f, p = {"year_from": 2022}, {"min_collisions": 3}
    r = hot_api.get(
        "/api/reports/sites.pdf",
        params={"f": json.dumps(f), "p": json.dumps(p), "top": 5, "title": "Exeter sites"},
    )

    assert r.status_code == 200
    assert 'filename="stats19-site-pack-' in r.headers["content-disposition"]
    url, timeout = captured[0]
    parsed = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qs(parsed.query)
    assert parsed.path == "/print/sites"
    assert json.loads(q["f"][0]) == f
    assert json.loads(q["p"][0]) == p
    assert q["top"] == ["5"] and q["title"] == ["Exeter sites"]
    assert timeout > 90  # many maps


def test_single_site_pdf(hot_api, captured):
    import urllib.parse

    r = hot_api.get("/api/reports/sites.pdf", params={"rank": 2})

    assert r.status_code == 200
    assert 'filename="stats19-site-2-' in r.headers["content-disposition"]
    assert urllib.parse.parse_qs(urllib.parse.urlparse(captured[0][0]).query)["rank"] == ["2"]


def test_site_pdf_unknown_rank_is_404(hot_api, captured):
    assert hot_api.get("/api/reports/sites.pdf", params={"rank": 9}).status_code == 404
    assert captured == []


def test_site_pack_limits(hot_api, captured):
    assert hot_api.get("/api/reports/sites.pdf", params={"top": 26}).status_code == 422
    assert hot_api.get("/api/reports/sites.pdf", params={"p": "{bad"}).status_code == 422
    assert captured == []


def test_cache_is_keyed_on_the_data_load(monkeypatch):
    """A new release (new successful etl.run) must not be served stale cached sites."""
    import stats19.api.hotspots as hotspots
    from stats19.api.filters import Filter
    from stats19.hotspots import HotspotParams

    loads = iter([7, 7, 8])
    calls: list[int] = []
    monkeypatch.setattr(hotspots.cache, "data_load", lambda conn: next(loads))
    monkeypatch.setattr(
        hotspots, "run_hotspots", lambda conn, f, p: calls.append(1) or {"sites": []}
    )
    hotspots.CACHE.clear()

    first = hotspots.cached_hotspots(None, Filter(), HotspotParams())
    hotspots.cached_hotspots(None, Filter(), HotspotParams())  # same load: cached
    hotspots.cached_hotspots(None, Filter(), HotspotParams())  # new load: recomputed

    assert len(calls) == 2
    assert first["data_load"] == 7
    hotspots.CACHE.clear()


def test_compare_reuses_the_area_baseline(hot_api, monkeypatch):
    """A site pack compares every site with the same area: count the area once."""
    import stats19.api.compare as compare

    calls: list[str] = []
    real = compare.indicator_counts
    monkeypatch.setattr(
        compare,
        "indicator_counts",
        lambda conn, f: calls.append(f.model_dump_json()) or real(conn, f),
    )
    a = {"collision_ids": [c["collision_index"] for c in SITE_A]}
    b = {"collision_ids": [c["collision_index"] for c in SITE_B]}

    _get(hot_api, "/api/compare", f=a, base={})
    _get(hot_api, "/api/compare", f=b, base={})

    assert len(calls) == 3  # site A, the area (once), site B


def test_cluster_sites_as_geojson_circles(hot_api):
    r = hot_api.get("/api/hotspots.geojson")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/geo+json")
    assert "stats19-cluster-sites.geojson" in r.headers["content-disposition"]
    a, b = r.json()["features"]
    assert a["geometry"]["type"] == "Polygon"
    ring = a["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1] and len(ring) == 4 * 16 + 1  # closed, 16 segments a quarter
    props = a["properties"]
    assert (props["rank"], props["collisions"], props["radius_m"]) == (1, 7, 50)
    assert props["label"] == "A38, near Sidwell Street, Exeter"
    assert props["collision_ids"].count(";") == 6
    # 50 m each way from the centre: about 0.00045 degrees of latitude
    lats = [p[1] for p in ring]
    assert max(lats) - min(lats) == pytest.approx(2 * 50 / 111_200, rel=0.02)
