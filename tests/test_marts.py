"""mart schema: road-user groups, summary aggregates, decoded views, catalogue, code counts."""

import pytest

from stats19 import db
from stats19.marts import ROAD_USER_GROUPS, group_for_code
from stats19.pipeline import ValidationFailed, last_success, process

from .test_pipeline_integration import (
    LENIENT,
    _collision,
)

# ------------------------------------------------------------------ unit


def test_road_user_groups_have_no_overlapping_codes():
    seen: dict[int, str] = {}
    for group, codes in ROAD_USER_GROUPS.items():
        for code in codes:
            assert code not in seen, f"code {code} in both {seen.get(code)} and {group}"
            seen[code] = group


def test_era_specific_codes_map_to_same_group_as_modern_codes():
    assert group_for_code(9) == group_for_code(109) == "car"
    assert group_for_code(5) == group_for_code(104) == "motorcycle"
    assert group_for_code(21) == group_for_code(113) == "goods_heavy"


def test_unknown_code_maps_to_none():
    assert group_for_code(4242) is None


# ------------------------------------------------------------------ integration

MART_COLLISIONS = [
    _collision(
        "1979A",
        1979,
        number_of_vehicles="2",
        number_of_casualties="2",
        location_easting_osgr="386590",
        location_northing_osgr="351990",
    ),
    _collision(
        "1980A", 1980, number_of_vehicles="1", number_of_casualties="1", light_conditions="2"
    ),
]
MART_VEHICLES = [
    {
        "collision_index": "1979A",
        "vehicle_reference": "1",
        "vehicle_type": "109",
        "age_of_driver": "45",
    },
    {
        "collision_index": "1979A",
        "vehicle_reference": "2",
        "vehicle_type": "1",
        "age_of_driver": "17",
    },
    {
        "collision_index": "1980A",
        "vehicle_reference": "1",
        "vehicle_type": "21",
        "age_of_driver": "-1",
    },
]
MART_CASUALTIES = [
    {
        "collision_index": "1979A",
        "vehicle_reference": "2",
        "casualty_reference": "1",
        "casualty_class": "1",
        "casualty_type": "1",
        "casualty_severity": "2",
        "casualty_adjusted_severity_serious": "1",
        "casualty_adjusted_severity_slight": "0",
    },
    {
        "collision_index": "1979A",
        "vehicle_reference": "1",
        "casualty_reference": "2",
        "casualty_class": "3",
        "casualty_type": "0",
        "casualty_severity": "1",
    },
    {
        "collision_index": "1980A",
        "vehicle_reference": "1",
        "casualty_reference": "1",
        "casualty_class": "1",
        "casualty_type": "21",
        "casualty_severity": "3",
        "casualty_adjusted_severity_serious": "0.25",
        "casualty_adjusted_severity_slight": "0.75",
    },
]


def _with_year(rows):
    """Child rows carry their collision's year, as in the real files."""
    return [{**r, "collision_year": r["collision_index"][:4]} for r in rows]


MART_VEHICLES = _with_year(MART_VEHICLES)
MART_CASUALTIES = _with_year(MART_CASUALTIES)


def _load(conn, files, thresholds=LENIENT):
    db.migrate(conn)
    return process(conn, files, last_success(conn), thresholds=thresholds)


def _one(conn, query, params=None):
    return conn.execute(query, params).fetchone()


@pytest.fixture
def loaded(db_conn, make_files):
    _load(db_conn, make_files(MART_COLLISIONS, MART_VEHICLES, MART_CASUALTIES))
    return db_conn


@pytest.mark.integration
def test_collision_summary_counts_recorded_casualties_and_vehicles(loaded):
    row = _one(
        loaded,
        """SELECT n_casualties, n_fatal, n_serious, n_slight,
                  n_vehicles_car, n_vehicles_pedal_cycle, n_vehicles_goods_heavy,
                  has_pedestrian_casualty, involves_pedal_cycle, involves_goods_heavy,
                  youngest_driver_age, oldest_driver_age
           FROM mart.collision WHERE collision_index = '1979A'""",
    )
    assert row == (2, 1, 1, 0, 1, 1, 0, True, True, False, 17, 45)


@pytest.mark.integration
def test_collision_summary_adjusted_severity_sums(loaded):
    assert _one(
        loaded,
        """SELECT adjusted_serious, adjusted_slight, youngest_driver_age
           FROM mart.collision WHERE collision_index = '1980A'""",
    ) == (0.25, 0.75, None)


@pytest.mark.integration
def test_mart_collision_has_one_row_per_core_collision(loaded):
    assert _one(loaded, "SELECT count(*) FROM mart.collision") == _one(
        loaded, "SELECT count(*) FROM core.collision"
    )


@pytest.mark.integration
def test_decoded_views_label_codes(loaded):
    assert _one(
        loaded,
        """SELECT light_conditions, light_conditions_label
           FROM mart.collision_decoded WHERE collision_index = '1980A'""",
    ) == (2, "Two")
    assert _one(
        loaded,
        """SELECT vehicle_type, road_user_group FROM mart.vehicle_decoded
           WHERE collision_index = '1979A' AND vehicle_reference = 1""",
    ) == (109, "car")
    assert _one(
        loaded,
        """SELECT casualty_class_label FROM mart.casualty_decoded
           WHERE collision_index = '1979A' AND casualty_reference = 1""",
    ) == ("One",)


@pytest.mark.integration
def test_field_catalog_reports_years_populated(loaded):
    row = _one(
        loaded,
        """SELECT kind, first_year, last_year, is_labelled
           FROM mart.field_catalog WHERE table_name = 'collision' AND field_name = 'light_conditions'""",
    )
    assert row == ("code", 1979, 1980, True)

    # easting only recorded for the 1979 row
    assert _one(
        loaded,
        """SELECT first_year, last_year, (populated_pct_by_year ->> '1980')::numeric
           FROM mart.field_catalog
           WHERE table_name = 'collision' AND field_name = 'location_easting_osgr'""",
    ) == (1979, 1979, 0)


@pytest.mark.integration
def test_field_catalog_covers_every_spec_column(loaded):
    from stats19.columns import TABLES

    expected = sum(len(s.columns) for s in TABLES.values())
    assert _one(loaded, "SELECT count(*) FROM mart.field_catalog") == (expected,)


@pytest.mark.integration
def test_code_counts_by_year(loaded):
    rows = loaded.execute(
        """SELECT collision_year, code, label, n FROM mart.code_counts
           WHERE table_name = 'vehicle' AND field_name = 'vehicle_type' ORDER BY 1, 2"""
    ).fetchall()
    # the test guide labels only codes -1/1/2
    assert rows == [(1979, 1, "One", 1), (1979, 109, None, 1), (1980, 21, None, 1)]


@pytest.mark.integration
def test_marts_follow_core_on_reload_and_no_previous_schemas_left(db_conn, make_files):
    _load(db_conn, make_files(MART_COLLISIONS, MART_VEHICLES, MART_CASUALTIES))
    more = [
        *MART_COLLISIONS,
        _collision("1980B", 1980, number_of_vehicles="0", number_of_casualties="0"),
    ]
    _load(db_conn, make_files(more, MART_VEHICLES, MART_CASUALTIES))

    assert _one(db_conn, "SELECT count(*) FROM mart.collision") == (3,)
    assert _one(db_conn, "SELECT count(*) FROM mart.collision_decoded") == (3,)
    schemas = {r[0] for r in db_conn.execute("SELECT nspname FROM pg_namespace")}
    assert {"core", "mart"} <= schemas
    assert not schemas & {"build", "build_mart", "core_previous", "mart_previous"}


@pytest.mark.integration
def test_failed_validation_leaves_existing_marts(db_conn, make_files):
    _load(db_conn, make_files(MART_COLLISIONS, MART_VEHICLES, MART_CASUALTIES))
    gap = [*MART_COLLISIONS, _collision("1982A", 1982)]

    with pytest.raises(ValidationFailed):
        _load(db_conn, make_files(gap, MART_VEHICLES, MART_CASUALTIES))

    assert _one(db_conn, "SELECT count(*) FROM mart.collision") == (2,)


@pytest.mark.integration
def test_unmapped_road_user_code_is_warned(db_conn, make_files):
    odd = [
        *MART_VEHICLES,
        {
            "collision_index": "1980A",
            "collision_year": "1980",
            "vehicle_reference": "2",
            "vehicle_type": "77",
        },
    ]
    run_id = _load(db_conn, make_files(MART_COLLISIONS, odd, MART_CASUALTIES))

    assert _one(
        db_conn,
        """SELECT severity, passed, detail FROM etl.run_check
           WHERE run_id = %s AND check_name = 'road_user_group_unmapped'""",
        (run_id,),
    ) == ("warn", False, "vehicle.vehicle_type=77 (1)")
