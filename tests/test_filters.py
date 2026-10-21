"""Filter model -> parameterised SQL (no client text ever reaches SQL)."""

import pytest
from psycopg import sql
from pydantic import ValidationError

from stats19.api.filters import Filter, compile_filter


def _render(f: Filter) -> tuple[str, dict]:
    clause, params = compile_filter(f)
    return clause.as_string(None), params


def test_empty_filter_is_true():
    text, params = _render(Filter())

    assert text == "TRUE"
    assert params == {}


def test_years_and_severity():
    text, params = _render(Filter(year_from=2020, year_to=2024, severity=[1, 2]))

    assert "c.collision_year >= %(year_from)s" in text
    assert "c.collision_year <= %(year_to)s" in text
    assert "c.collision_severity = ANY(%(severity)s)" in text
    assert params == {"year_from": 2020, "year_to": 2024, "severity": [1, 2]}


def test_involves_flags_use_whitelisted_columns():
    text, _ = _render(Filter(involves=["pedal_cycle", "goods_heavy"]))

    assert '"involves_pedal_cycle"' in text and '"involves_goods_heavy"' in text
    assert " OR " in text  # any of the selected road users


def test_unknown_involves_rejected():
    with pytest.raises(ValidationError):
        Filter(involves=["tractor; DROP TABLE x"])


def test_collision_field_condition():
    text, params = _render(
        Filter(fields=[{"table": "collision", "field": "light_conditions", "values": [4, 5, 6, 7]}])
    )

    assert 'c."light_conditions" = ANY(%(f0)s)' in text
    assert params["f0"] == [4, 5, 6, 7]


def test_child_table_condition_uses_exists():
    text, params = _render(
        Filter(fields=[{"table": "vehicle", "field": "vehicle_manoeuvre", "values": [4]}])
    )

    assert "EXISTS (SELECT 1 FROM core.vehicle x" in text
    assert 'x."vehicle_manoeuvre" = ANY(%(f0)s)' in text
    assert params["f0"] == [4]


@pytest.mark.parametrize(
    "bad",
    [
        {"table": "collision", "field": "collision_index", "values": ["x"]},  # not a code field
        {"table": "collision", "field": "nope", "values": [1]},
        {"table": "collision", "field": "light_conditions; --", "values": [1]},
        {"table": "secrets", "field": "light_conditions", "values": [1]},
    ],
)
def test_field_conditions_are_whitelisted(bad):
    with pytest.raises(ValidationError):
        Filter(fields=[bad])


def test_measure_between():
    text, params = _render(
        Filter(
            fields=[
                {"table": "vehicle", "field": "age_of_driver", "op": "between", "values": [17, 24]}
            ]
        )
    )

    assert 'x."age_of_driver" BETWEEN %(f0_lo)s AND %(f0_hi)s' in text
    assert params["f0_lo"] == 17 and params["f0_hi"] == 24


def test_between_needs_two_values():
    with pytest.raises(ValidationError):
        Filter(
            fields=[{"table": "vehicle", "field": "age_of_driver", "op": "between", "values": [17]}]
        )


def test_time_of_day_wraps_midnight():
    text, params = _render(Filter(time_from="22:00", time_to="04:00"))

    assert "c.collision_time >= %(time_from)s OR c.collision_time < %(time_to)s" in text


def test_day_of_week_and_date_range():
    text, params = _render(Filter(date_from="2024-01-01", date_to="2024-03-31", day_of_week=[1, 7]))

    assert "c.collision_date >= %(date_from)s" in text
    assert "c.collision_day_of_week" not in text
    assert "c.day_of_week = ANY(%(day_of_week)s)" in text


def test_radius_area():
    text, params = _render(
        Filter(area={"type": "radius", "lon": -3.53, "lat": 50.72, "radius_m": 500})
    )

    assert "ST_DWithin(c.geom_bng" in text
    assert params["area_radius_m"] == 500


def test_radius_limits():
    with pytest.raises(ValidationError):
        Filter(area={"type": "radius", "lon": -3.53, "lat": 50.72, "radius_m": 50_000})


def test_polygon_area():
    poly = {
        "type": "Polygon",
        "coordinates": [[[-3.6, 50.7], [-3.4, 50.7], [-3.4, 50.8], [-3.6, 50.7]]],
    }
    text, params = _render(Filter(area={"type": "polygon", "geometry": poly}))

    assert "ST_Intersects(c.geom_bng" in text
    assert '"Polygon"' in params["area_geojson"]


def test_authority_area():
    text, params = _render(
        Filter(
            area={"type": "authority", "boundary_type": "highway_authority", "code": "E10000008"}
        )
    )

    assert "FROM geo.boundary b" in text
    assert params["area_code"] == "E10000008"


def test_bbox_clause_for_tiles():
    f = Filter(year_from=2024)
    clause, _ = compile_filter(f, extra=[sql.SQL("TRUE")])

    assert clause.as_string(None).count("TRUE") == 1


def test_filter_round_trips_via_json():
    f = Filter(year_from=2020, severity=[1], involves=["motorcycle"])

    assert Filter.model_validate_json(f.model_dump_json()) == f


def test_collision_ids_select_exact_collisions():
    text, params = _render(Filter(collision_ids=["2023010000001", "2023010000002"]))

    assert "c.collision_index = ANY(%(collision_ids)s)" in text
    assert params == {"collision_ids": ["2023010000001", "2023010000002"]}


@pytest.mark.parametrize("bad", [["x'; DROP TABLE y"], [""], ["A" * 21]])
def test_collision_ids_are_validated(bad):
    with pytest.raises(ValidationError):
        Filter(collision_ids=bad)


def test_collision_ids_are_capped():
    with pytest.raises(ValidationError):
        Filter(collision_ids=[f"C{i}" for i in range(1001)])
