"""Stick diagram data: one entry per collision with its vehicles and casualties."""

import json

import pytest

pytestmark = pytest.mark.integration


def test_sticks_include_vehicles_and_casualties(api):
    d = api.get("/api/sticks").json()["data"]

    assert d["total"] == 2
    ids = [s["collision_index"] for s in d["sticks"]]
    assert ids == ["1979A", "1980A"]  # oldest first
    s = d["sticks"][1]
    assert {
        "collision_date",
        "severity",
        "light_conditions",
        "light_conditions_label",
        "speed_limit",
        "road",
    } <= set(s)
    assert [v["vehicle_reference"] for v in s["vehicles"]] == [1, 2]
    v = s["vehicles"][0]
    assert {
        "vehicle_type_label",
        "road_user_group",
        "vehicle_manoeuvre",
        "vehicle_manoeuvre_historic",
        "first_point_of_impact",
        "skidding_and_overturning",
        "age_of_driver",
    } <= set(v)
    assert [k["casualty_reference"] for k in s["casualties"]] == [1, 2]
    assert {"casualty_class", "casualty_severity", "age_of_casualty", "vehicle_reference"} <= set(
        s["casualties"][0]
    )


def test_sticks_respect_filter(api):
    d = api.get("/api/sticks", params={"f": json.dumps({"year_from": 1980})}).json()["data"]

    assert [s["collision_index"] for s in d["sticks"]] == ["1980A"]


def test_sticks_too_many_is_refused(api, monkeypatch):
    import stats19.api.sticks as sticks

    monkeypatch.setattr(sticks, "MAX_STICKS", 1)
    r = api.get("/api/sticks")

    assert r.status_code == 413
    assert r.json()["error"]["code"] == "too_large"
