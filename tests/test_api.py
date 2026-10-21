"""API: health, meta, search, areas (against PostGIS with fixture data)."""

import pytest

pytestmark = pytest.mark.integration


def test_health(api):
    r = api.get("/api/health")

    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok" and body["data"]["database"] is True
    assert set(body["data"]["version"]) == {"commit", "built"}  # FU-050
    assert r.headers["X-Request-Ref"]


def test_meta_reports_coverage_fields_and_codes(api):
    body = api.get("/api/meta").json()

    assert body["success"] is True
    data = body["data"]
    assert data["coverage"] == {"first_year": 1979, "last_year": 1980, "collisions": 2}
    assert data["last_run"]["status"] == "success"
    light = next(
        f
        for f in data["fields"]
        if f["table_name"] == "collision" and f["field_name"] == "light_conditions"
    )
    assert light["kind"] == "code"
    assert {"code": 1, "label": "One"} in light["codes"]
    assert data["limits"] == {"summary": 200_000, "export_csv": 100_000, "export_xlsx": 25_000}
    assert {d["dataset"] for d in data["reference"]} == {
        "postcode",
        "place",
        "boundary",
        "value_of_prevention",
        "road_network",
        "traffic",
        "traffic_links",
        "osm_nodes",
        "junctions",
        "junction_collisions",
        "collision_links",
        "context",
        "population",
        "authorities",
        "safety",
    }


def test_meta_is_cached_until_a_new_load_or_refresh(api, db_conn):
    """Meta counts every collision, so it's cached; a load or reference refresh renews it."""
    assert api.get("/api/meta").json()["data"]["coverage"]["last_year"] == 1980
    db_conn.execute("UPDATE core.collision SET collision_year = 1981")
    db_conn.commit()

    assert api.get("/api/meta").json()["data"]["coverage"]["last_year"] == 1980  # cached

    db_conn.execute(
        "UPDATE geo.reference_refresh SET refreshed_at = now() + interval '1 hour'"
        " WHERE dataset = 'boundary'"
    )
    db_conn.commit()
    assert api.get("/api/meta").json()["data"]["coverage"]["last_year"] == 1981

    db_conn.execute("UPDATE core.collision SET collision_year = 1982")
    db_conn.execute("INSERT INTO etl.run (source_updated_at, status) VALUES (now(), 'success')")
    db_conn.commit()
    assert api.get("/api/meta").json()["data"]["coverage"]["first_year"] == 1982


@pytest.mark.parametrize("q", ["EX1 1AE", "ex11ae", "EX1 1"])
def test_search_postcode(api, q):
    results = api.get("/api/search", params={"q": q}).json()["data"]

    assert results[0]["type"] == "postcode"
    assert results[0]["label"] == "EX1 1AE"
    assert -3.6 < results[0]["lon"] < -3.4 and 50.6 < results[0]["lat"] < 50.8
    assert len(results[0]["bbox"]) == 4


def test_search_place_and_road_prefix(api):
    results = api.get("/api/search", params={"q": "sidw"}).json()["data"]

    assert results[0]["label"] == "Sidwell Street"
    assert results[0]["type"] == "road"
    assert results[0]["sublabel"] == "Exeter, Devon"


def test_search_validates_query_length(api):
    r = api.get("/api/search", params={"q": "x"})

    assert r.status_code == 422
    assert r.json()["success"] is False
    assert r.json()["error"]["code"] == "validation_error"


def test_areas_list_and_detail(api):
    listing = api.get("/api/areas", params={"type": "highway_authority"}).json()["data"]
    assert listing == [{"code": "E10000008", "name": "Devon"}]

    detail = api.get("/api/areas/highway_authority/E10000008").json()["data"]
    assert detail["name"] == "Devon"
    assert detail["geometry"]["type"] in ("Polygon", "MultiPolygon")
    assert len(detail["bbox"]) == 4


def test_areas_unknown_type_rejected(api):
    assert api.get("/api/areas", params={"type": "parish"}).status_code == 422


def test_area_not_found(api):
    r = api.get("/api/areas/district/E99999999")

    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_search_typo_falls_back_to_fuzzy(api):
    results = api.get("/api/search", params={"q": "sidwel street"}).json()["data"]

    assert results[0]["label"] == "Sidwell Street"


def test_search_exact_prefix_has_no_fuzzy_noise(api):
    labels = [
        r["label"] for r in api.get("/api/search", params={"q": "sidwell street"}).json()["data"]
    ]

    assert labels == ["Sidwell Street"]
