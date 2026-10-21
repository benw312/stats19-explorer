"""Saved schemes (V5, PLAN-011 S1): the API and its write safeguards."""

import os
from types import SimpleNamespace
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from stats19 import db
from stats19.api import schemes, writes
from stats19.api.app import create_app
from stats19.api.limits import RateLimit
from stats19.api.org import DEFAULT_ORG

SAME_SITE = {"Origin": "http://testserver"}

# a small square in Bath, and a short line along a road there
SQUARE = {
    "type": "Polygon",
    "coordinates": [
        [[-2.361, 51.381], [-2.359, 51.381], [-2.359, 51.379], [-2.361, 51.379], [-2.361, 51.381]]
    ],
}
LINE = {"type": "LineString", "coordinates": [[-2.361, 51.381], [-2.355, 51.383]]}


def scheme(**overrides) -> dict:
    return {
        "name": "London Road signals",
        "description": "New signals at the London Road junction.",
        "measure": "signals",
        "site_type": "junction",
        "site_ref": "J123",
        "geometry": SQUARE,
        "works_start": "2021-03-01",
        "works_end": "2021-06-30",
        "cost": 250000,
        "fyrr": {
            "collisions_per_year": 2.4,
            "value_per_collision": 120000,
            "reduction_pct": 30,
            "basis": "Empirical Bayes estimate",
            "prices_year": 2024,
        },
    } | overrides


@pytest.fixture
def client(db_conn, monkeypatch):
    monkeypatch.setattr(writes, "LIMIT", RateLimit(1000, 60))
    db.migrate(db_conn)
    with TestClient(create_app(os.environ["STATS19_TEST_DATABASE_URL"])) as c:
        yield c


def create(client, **overrides):
    return client.post("/api/schemes", json=scheme(**overrides), headers=SAME_SITE)


# --- unit -------------------------------------------------------------------------------


def test_every_measure_code_has_a_label():
    assert set(get_args(schemes.Measure)) == set(schemes.MEASURES)


def test_the_editor_is_the_access_email_or_lan():
    assert writes.editor(SimpleNamespace(state=SimpleNamespace(access_email="a@b.uk"))) == "a@b.uk"
    assert writes.editor(SimpleNamespace(state=SimpleNamespace())) == "LAN"


def test_footprint_must_match_the_site_type():
    with pytest.raises(ValueError, match="must be a line"):
        schemes.SchemeIn(**scheme(site_type="link"))
    with pytest.raises(ValueError, match="must be an area"):
        schemes.SchemeIn(**scheme(geometry=LINE))
    assert schemes.SchemeIn(**scheme(site_type="route", geometry=LINE)).site_type == "route"


def test_a_footprint_with_too_many_points_is_refused():
    ring = [[-2.0 + i * 1e-6, 51.0] for i in range(schemes.MAX_VERTICES)] + [[-2.0, 51.0]]
    with pytest.raises(ValueError, match="more than"):
        schemes.SchemeIn(**scheme(geometry={"type": "Polygon", "coordinates": [ring]}))


# --- API --------------------------------------------------------------------------------


@pytest.mark.integration
def test_options_list_the_measures(client):
    data = client.get("/api/schemes/options").json()["data"]
    assert {"code": "signals", "label": "Traffic signals (new or upgraded)"} in data["measures"]
    assert data["site_types"] == ["junction", "cluster", "area", "link", "route"]


@pytest.mark.integration
def test_create_then_read_and_list(client, db_conn):
    r = create(client)

    assert r.status_code == 201, r.text
    s = r.json()["data"]
    assert s["name"] == "London Road signals"
    assert s["version"] == 1
    assert s["created_by"] == s["updated_by"] == "LAN"
    assert s["fyrr"]["reduction_pct"] == 30
    assert s["cost"] == 250000
    assert s["geometry"]["type"] == "Polygon"
    lon, lat = s["geometry"]["coordinates"][0][0]
    assert lon == pytest.approx(-2.361, abs=1e-5) and lat == pytest.approx(51.381, abs=1e-5)
    assert -2.361 < s["point"][0] < -2.359

    assert client.get(f"/api/schemes/{s['id']}").json()["data"]["name"] == s["name"]
    listed = client.get("/api/schemes").json()
    assert [x["id"] for x in listed["data"]] == [s["id"]]
    assert "geometry" not in listed["data"][0]

    org = db_conn.execute("SELECT org_id FROM app.scheme").fetchone()[0]
    assert org == DEFAULT_ORG


@pytest.mark.integration
@pytest.mark.parametrize(
    "headers, kwargs, status",
    [
        ({}, {"json": scheme()}, 403),  # no Origin
        ({"Origin": "https://evil.example"}, {"json": scheme()}, 403),
        ({"Origin": "null"}, {"json": scheme()}, 403),
        (SAME_SITE, {"data": {"name": "x"}}, 415),  # a form post
        (SAME_SITE | {"Content-Type": "text/plain"}, {"content": "{}"}, 415),
    ],
)
def test_writes_need_same_site_json(client, db_conn, headers, kwargs, status):
    r = client.post("/api/schemes", headers=headers, **kwargs)

    assert r.status_code == status
    assert db_conn.execute("SELECT count(*) FROM app.scheme").fetchone()[0] == 0


@pytest.mark.integration
def test_writes_are_rate_limited(client, monkeypatch):
    monkeypatch.setattr(writes, "LIMIT", RateLimit(1, 60))
    assert create(client).status_code == 201
    r = create(client, name="Second")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"


@pytest.mark.integration
@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"site_type": "link"}, "must be a line"),
        ({"works_start": "2021-06-30", "works_end": "2021-03-01"}, "can't end before"),
        ({"works_start": "1950-01-01"}, "between 1979"),
        ({"before_years": 6}, "less than or equal to 5"),
        ({"measure": "bollards"}, "Input should be"),
        ({"surprise": 1}, "Extra inputs"),
        ({"name": "   "}, "at least 1 character"),
        (
            {"fyrr": {"collisions_per_year": 1, "value_per_collision": 1, "reduction_pct": 0}},
            "greater than 0",
        ),
        ({"geometry": {"type": "Polygon", "coordinates": [["x"]]}}, "nested correctly"),
        ({"geometry": {"type": "Polygon", "coordinates": [[["a", "b"]]]}}, "[longitude, latitude]"),
        ({"geometry": {"type": "LineString", "coordinates": []}}, "nested correctly"),
    ],
)
def test_bad_input_is_refused_with_a_reason(client, overrides, message):
    r = create(client, **overrides)

    assert r.status_code == 422
    assert message in str(r.json()["error"]["details"])


@pytest.mark.integration
@pytest.mark.parametrize(
    "geometry, message",
    [
        (  # a bow tie: the ring crosses itself
            {
                "type": "Polygon",
                "coordinates": [
                    [[-2.36, 51.38], [-2.35, 51.39], [-2.35, 51.38], [-2.36, 51.39], [-2.36, 51.38]]
                ],
            },
            "isn't a valid shape (self-intersection)",
        ),
        (  # Paris
            {
                "type": "Polygon",
                "coordinates": [
                    [[2.35, 48.85], [2.36, 48.85], [2.36, 48.86], [2.35, 48.86], [2.35, 48.85]]
                ],
            },
            "in Great Britain",
        ),
        (  # most of England
            {
                "type": "Polygon",
                "coordinates": [
                    [[-3.0, 51.0], [0.0, 51.0], [0.0, 54.0], [-3.0, 54.0], [-3.0, 51.0]]
                ],
            },
            "too large",
        ),
        ({"type": "Polygon", "coordinates": [[[-2.36, 51.38]]]}, "isn't a valid shape."),
    ],
)
def test_bad_footprints_are_refused(client, db_conn, geometry, message):
    r = create(client, geometry=geometry)

    assert r.status_code == 422, r.text
    assert message in r.json()["error"]["message"]
    assert db_conn.execute("SELECT count(*) FROM app.scheme").fetchone()[0] == 0


@pytest.mark.integration
def test_names_are_unique_ignoring_case_until_deleted(client):
    first = create(client).json()["data"]
    r = create(client, name="LONDON ROAD SIGNALS")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "name_taken"

    client.delete(f"/api/schemes/{first['id']}", headers=SAME_SITE)
    assert create(client, name="london road signals").status_code == 201


@pytest.mark.integration
def test_edit_bumps_the_version_and_refuses_a_stale_one(client):
    s = create(client).json()["data"]
    edit = scheme(name="London Road signals (phase 1)", site_type="route", geometry=LINE)

    r = client.put(f"/api/schemes/{s['id']}", json=edit | {"version": 1}, headers=SAME_SITE)
    assert r.status_code == 200, r.text
    edited = r.json()["data"]
    assert edited["version"] == 2
    assert edited["site_type"] == "route"
    assert edited["geometry"]["type"] == "LineString"
    assert edited["created_at"] == s["created_at"]

    stale = client.put(f"/api/schemes/{s['id']}", json=edit | {"version": 1}, headers=SAME_SITE)
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale"

    no_version = client.put(f"/api/schemes/{s['id']}", json=edit, headers=SAME_SITE)
    assert no_version.status_code == 422


@pytest.mark.integration
def test_unknown_or_deleted_schemes_are_not_found(client, db_conn):
    missing = "00000000-0000-0000-0000-00000000abcd"
    assert client.get(f"/api/schemes/{missing}").status_code == 404
    edit = scheme() | {"version": 1}
    assert client.put(f"/api/schemes/{missing}", json=edit, headers=SAME_SITE).status_code == 404
    assert client.delete(f"/api/schemes/{missing}", headers=SAME_SITE).status_code == 404

    s = create(client).json()["data"]
    r = client.delete(f"/api/schemes/{s['id']}", headers=SAME_SITE)
    assert r.status_code == 200
    assert client.get(f"/api/schemes/{s['id']}").status_code == 404
    assert client.get("/api/schemes").json()["data"] == []
    # only marked, so it can be recovered
    row = db_conn.execute("SELECT deleted_by FROM app.scheme").fetchone()
    assert row == ("LAN",)


@pytest.mark.integration
def test_read_write_must_be_the_first_transaction(db_conn):
    db.migrate(db_conn)
    db_conn.execute("SELECT 1")
    with pytest.raises(RuntimeError, match="first transaction"), writes.read_write(db_conn):
        pass


# around the fixture's fatal 1979 collision, at (-2.20157, 53.06498)
AROUND_1979A = {
    "type": "Polygon",
    "coordinates": [
        [[-2.203, 53.064], [-2.200, 53.064], [-2.200, 53.066], [-2.203, 53.066], [-2.203, 53.064]]
    ],
}


@pytest.mark.integration
def test_collisions_by_year_in_an_area_footprint_with_its_periods(api, monkeypatch):
    monkeypatch.setattr(writes, "LIMIT", RateLimit(1000, 60))
    s = api.post(
        "/api/schemes",
        json=scheme(
            geometry=AROUND_1979A,
            works_start="1980-03-01",
            works_end="1980-06-30",
            before_years=2,
        ),
        headers=SAME_SITE,
    ).json()["data"]
    assert s["status"]["stage"] == "monitoring"
    assert s["status"]["after_months"] == 6  # the fixture's data ends in 1980
    assert s["status"]["data_end"] == "1980-12-31"

    r = api.get(f"/api/schemes/{s['id']}/collisions")

    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["by_year"] == [
        {"year": 1979, "fatal": 1, "serious": 0, "slight": 0},
        {"year": 1980, "fatal": 0, "serious": 0, "slight": 0},
    ]
    assert d["before"] == {"start": "1978-03-01", "end": "1980-02-29"}
    assert d["after"] == {"start": "1980-07-01", "end": "1983-06-30"}
    # a junction scheme counts junction collisions only, as its evaluation does (FU-057)
    assert d["match"] == {"kind": "area", "within_m": 0.0, "rule": "junction"}


@pytest.mark.integration
@pytest.mark.parametrize("offset_deg, near", [(0.0001, True), (0.002, False)])
def test_a_line_footprint_counts_collisions_within_25_m(api, monkeypatch, offset_deg, near):
    monkeypatch.setattr(writes, "LIMIT", RateLimit(1000, 60))
    lat = 53.06498 + offset_deg  # 0.0001° ≈ 11 m north; 0.002° ≈ 220 m
    line = {"type": "LineString", "coordinates": [[-2.205, lat], [-2.198, lat]]}
    s = api.post(
        "/api/schemes",
        json=scheme(site_type="link", geometry=line, works_start=None, works_end=None),
        headers=SAME_SITE,
    ).json()["data"]
    assert s["status"]["stage"] == "undated"

    d = api.get(f"/api/schemes/{s['id']}/collisions").json()["data"]

    assert d["match"] == {"kind": "line", "within_m": 25.0, "rule": "not_junction"}
    assert d["before"] is None and d["after"] is None
    assert [y["year"] for y in d["by_year"]] == [1979, 1980]
    assert d["by_year"][0]["fatal"] == (1 if near else 0)


@pytest.mark.integration
def test_collisions_of_an_unknown_scheme_are_not_found(api):
    r = api.get("/api/schemes/00000000-0000-0000-0000-00000000abcd/collisions")
    assert r.status_code == 404


@pytest.mark.integration
def test_the_list_gives_each_scheme_its_status(client):
    create(client)

    row = client.get("/api/schemes").json()["data"][0]

    # nothing loaded yet in this fixture: the after period has no data
    assert row["status"] == {
        "stage": "monitoring",
        "after_months": 0,
        "after_months_wanted": 36,
        "data_end": None,
    }
