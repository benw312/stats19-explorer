import pytest

from stats19.columns import (
    TABLES,
    HeaderError,
    Kind,
    check_header,
    normalise_header,
    parse_failure_exprs,
    typed_select_list,
)


def test_every_table_starts_with_collision_index_key():
    for spec in TABLES.values():
        assert spec.columns[0].name == "collision_index"
        assert spec.columns[0].kind is Kind.KEY_TEXT


def test_kinds_are_distinct_members_not_aliases():
    assert len(list(Kind)) == len(Kind.__members__)
    assert Kind.KEY_INT is not Kind.CODE
    assert Kind.KEY_TEXT is not Kind.TEXT


def test_key_columns_are_key_kinds():
    for spec in TABLES.values():
        for name in spec.primary_key:
            kind = next(c.kind for c in spec.columns if c.name == name)
            assert kind in (Kind.KEY_TEXT, Kind.KEY_INT), (spec.name, name)


def test_column_names_unique_per_table():
    for spec in TABLES.values():
        names = [c.name for c in spec.columns]
        assert len(names) == len(set(names)), spec.name


def test_normalise_header_maps_legacy_accident_names():
    header = ["Accident_Index", " accident_year", "accident_reference", "accident_severity"]

    assert normalise_header(header) == [
        "collision_index",
        "collision_year",
        "collision_ref_no",
        "collision_severity",
    ]


def test_normalise_header_strips_utf8_bom():
    assert normalise_header(["﻿collision_index"]) == ["collision_index"]


def test_check_header_accepts_exact_header():
    spec = TABLES["casualty"]
    result = check_header(spec, [c.name for c in spec.columns])

    assert result.missing == []
    assert result.unexpected == []


def test_check_header_reports_unexpected_columns_without_failing():
    spec = TABLES["casualty"]
    header = [c.name for c in spec.columns] + ["brand_new_field"]

    result = check_header(spec, header)

    assert result.unexpected == ["brand_new_field"]


def test_check_header_fails_when_required_column_missing():
    spec = TABLES["vehicle"]
    header = [c.name for c in spec.columns if c.name != "vehicle_reference"]

    with pytest.raises(HeaderError, match="vehicle_reference"):
        check_header(spec, header)


def test_check_header_tolerates_missing_optional_column():
    spec = TABLES["collision"]
    optional = [c.name for c in spec.columns if c.optional]
    assert optional, "collision spec should mark newer columns optional"

    header = [c.name for c in spec.columns if not c.optional]
    result = check_header(spec, header)

    assert sorted(result.missing) == sorted(optional)


def test_typed_select_list_casts_by_kind():
    spec = TABLES["vehicle"]
    sql = typed_select_list(spec, available={c.name for c in spec.columns})

    assert "etl.to_code(r.vehicle_type) AS vehicle_type" in sql
    assert "etl.to_measure(r.age_of_driver) AS age_of_driver" in sql
    assert "NULLIF(btrim(r.generic_make_model), '') AS generic_make_model" in sql


def test_parse_failure_exprs_skip_text_and_use_plain_int_for_measures():
    spec = TABLES["vehicle"]
    exprs = dict(parse_failure_exprs(spec, available={c.name for c in spec.columns}))

    assert "generic_make_model" not in exprs
    assert "collision_index" not in exprs
    assert exprs["age_of_driver"] == (
        "(btrim(r.age_of_driver) <> '' AND etl.to_int(r.age_of_driver) IS NULL)"
    )
    assert "etl.to_code(r.vehicle_type)" in exprs["vehicle_type"]


def test_typed_select_list_fills_missing_optional_columns_with_typed_null():
    spec = TABLES["collision"]
    available = {c.name for c in spec.columns if not c.optional}

    sql = typed_select_list(spec, available=available)

    assert "NULL::smallint AS collision_injury_based" in sql


def test_speed_limit_is_a_measure_not_a_code():
    kind = next(c.kind for c in TABLES["collision"].columns if c.name == "speed_limit")

    assert kind is Kind.MEASURE


def test_unmatched_guide_fields_ignores_known_and_reports_unknown():
    from stats19.columns import unmatched_guide_fields

    pairs = {
        ("collision", "light_conditions"),
        ("vehicle", "made_up_field"),
        ("historical_revisions", "variable"),  # other dataset in the guide: ignored
    }

    assert unmatched_guide_fields(pairs) == [("vehicle", "made_up_field")]


def test_core_name_maps_renamed_collision_columns():
    from stats19.columns import core_name

    assert core_name("collision", "date") == "collision_date"
    assert core_name("collision", "time") == "collision_time"
    assert core_name("vehicle", "vehicle_type") == "vehicle_type"
