"""End-to-end tests against a real PostGIS (set STATS19_TEST_DATABASE_URL)."""

import pytest

from stats19 import db
from stats19.pipeline import ValidationFailed, last_success, process
from stats19.validate import Thresholds

pytestmark = pytest.mark.integration

LENIENT = Thresholds(max_quarantine_ratio=1.0, max_parse_failure_ratio=1.0, first_year=1979)


def _collision(index, year, **kw):
    return {
        "collision_index": index,
        "collision_year": str(year),
        "collision_ref_no": "0" + index,
        "date": f"15/06/{year}",
        **kw,
    }


GOOD_COLLISIONS = [
    # 1979 row: BNG only, no lon/lat -> geometry derived by transform.
    _collision(
        "1979A",
        1979,
        location_easting_osgr="386590",
        location_northing_osgr="351990",
        number_of_vehicles="1",
        number_of_casualties="1",
    ),
    _collision(
        "1980A",
        1980,
        longitude="-1.2642",
        latitude="54.5665",
        time="09:35",
        number_of_vehicles="2",
        number_of_casualties="2",
    ),
    # exact duplicate of the row above -> collapsed silently
    _collision(
        "1980A",
        1980,
        longitude="-1.2642",
        latitude="54.5665",
        time="09:35",
        number_of_vehicles="2",
        number_of_casualties="2",
    ),
    # conflicting duplicate -> both quarantined
    _collision("1980B", 1980, collision_severity="1"),
    _collision("1980B", 1980, collision_severity="2"),
    # blank key -> quarantined
    _collision("", 1980),
]

GOOD_VEHICLES = [
    {"collision_index": "1979A", "vehicle_reference": "1", "age_of_driver": "45"},
    {"collision_index": "1980A", "vehicle_reference": "1", "age_of_driver": "-1"},
    {"collision_index": "1980A", "vehicle_reference": "2"},
    {"collision_index": "NOPE", "vehicle_reference": "1"},  # orphan collision
]

GOOD_CASUALTIES = [
    {"collision_index": "1979A", "vehicle_reference": "1", "casualty_reference": "1"},
    {"collision_index": "1980A", "vehicle_reference": "1", "casualty_reference": "1"},
    # vehicle 7 doesn't exist -> kept, vehicle_reference NULL, logged in quarantine
    {"collision_index": "1980A", "vehicle_reference": "7", "casualty_reference": "2"},
    {"collision_index": "NOPE", "vehicle_reference": "1", "casualty_reference": "1"},
]


def _load(conn, files, thresholds=LENIENT):
    db.migrate(conn)
    return process(conn, files, last_success(conn), thresholds=thresholds)


def _one(conn, query, params=None):
    return conn.execute(query, params).fetchone()


def test_migrate_is_idempotent(db_conn):
    first = db.migrate(db_conn)
    second = db.migrate(db_conn)

    assert first == [
        "001_etl.sql",
        "002_geo.sql",
        "003_place_bbox_index.sql",
        "004_api_role.sql",
        "005_spatial_indexes.sql",
        "006_derived_pending.sql",
        "007_app_schemes.sql",
        "008_app_feedback.sql",
    ]
    assert second == []


def test_full_load_builds_keyed_core(db_conn, make_files):
    run_id = _load(db_conn, make_files(GOOD_COLLISIONS, GOOD_VEHICLES, GOOD_CASUALTIES))

    assert _one(db_conn, "SELECT status FROM etl.run WHERE run_id = %s", (run_id,)) == ("success",)
    counts = _one(
        db_conn,
        """SELECT (SELECT count(*) FROM core.collision), (SELECT count(*) FROM core.vehicle),
                  (SELECT count(*) FROM core.casualty)""",
    )
    assert counts == (2, 3, 3)

    reasons = dict(
        db_conn.execute(
            "SELECT table_name || ':' || reason, count(*) FROM core.quarantine GROUP BY 1"
        ).fetchall()
    )
    assert reasons == {
        "collision:conflicting_duplicate_key": 2,
        "collision:null_key": 1,
        "vehicle:orphan_collision": 1,
        "casualty:orphan_collision": 1,
        "casualty:orphan_vehicle_unlinked": 1,
    }


def test_core_has_enforced_keys(db_conn, make_files):
    _load(db_conn, make_files(GOOD_COLLISIONS, GOOD_VEHICLES, GOOD_CASUALTIES))

    constraints = {
        r[0]
        for r in db_conn.execute(
            """SELECT conname FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace
               WHERE n.nspname = 'core'"""
        )
    }
    assert {
        "collision_pkey",
        "vehicle_pkey",
        "casualty_pkey",
        "vehicle_collision_fk",
        "casualty_collision_fk",
        "casualty_vehicle_fk",
    } <= constraints


def test_types_and_sentinels(db_conn, make_files):
    _load(db_conn, make_files(GOOD_COLLISIONS, GOOD_VEHICLES, GOOD_CASUALTIES))

    date, time, ts, ref = _one(
        db_conn,
        """SELECT collision_date, collision_time, collision_datetime, collision_ref_no
           FROM core.collision WHERE collision_index = '1980A'""",
    )
    assert (str(date), str(time), str(ts), ref) == (
        "1980-06-15",
        "09:35:00",
        "1980-06-15 09:35:00",
        "01980A",
    )

    # measure -1 -> NULL; code -1 kept
    assert _one(
        db_conn,
        """SELECT age_of_driver FROM core.vehicle
                             WHERE collision_index = '1980A' AND vehicle_reference = 1""",
    ) == (None,)
    assert _one(
        db_conn,
        """SELECT age_of_driver FROM core.vehicle
                             WHERE collision_index = '1979A'""",
    ) == (45,)
    assert _one(
        db_conn,
        """SELECT vehicle_reference FROM core.casualty
                             WHERE collision_index = '1980A' AND casualty_reference = 2""",
    ) == (None,)


def test_geometry_from_lonlat_or_bng(db_conn, make_files):
    _load(db_conn, make_files(GOOD_COLLISIONS, GOOD_VEHICLES, GOOD_CASUALTIES))

    rows = dict(
        (r[0], r[1:])
        for r in db_conn.execute(
            """SELECT collision_index, ST_X(geom_wgs84), ST_Y(geom_wgs84), geom_bng IS NOT NULL
               FROM core.collision"""
        )
    )
    assert rows["1980A"][:2] == (-1.2642, 54.5665)
    lon, lat, has_bng = rows["1979A"]
    assert has_bng
    assert -2.3 < lon < -2.1 and 53.0 < lat < 53.1  # Staffordshire


def test_lookups_loaded_with_aliases_and_conversions(db_conn, make_files):
    _load(db_conn, make_files(GOOD_COLLISIONS, GOOD_VEHICLES, GOOD_CASUALTIES))

    assert _one(
        db_conn,
        """SELECT label FROM core.lookup_code
                            WHERE table_name = 'collision' AND field_name = 'light_conditions'
                              AND code = '1'""",
    ) == ("One",)
    assert _one(db_conn, "SELECT count(*) FROM core.lookup_conversion") == (1,)


def test_raw_tables_dropped_after_success(db_conn, make_files):
    _load(db_conn, make_files(GOOD_COLLISIONS, GOOD_VEHICLES, GOOD_CASUALTIES))

    assert _one(db_conn, "SELECT count(*) FROM pg_tables WHERE schemaname = 'raw'") == (0,)


def test_rerun_is_idempotent(db_conn, make_files):
    files = make_files(GOOD_COLLISIONS, GOOD_VEHICLES, GOOD_CASUALTIES)
    _load(db_conn, files)
    _load(db_conn, files)

    assert _one(db_conn, "SELECT count(*) FROM core.collision") == (2,)
    assert _one(db_conn, "SELECT count(*) FROM etl.run WHERE status = 'success'") == (2,)


def test_failed_validation_keeps_existing_core(db_conn, make_files):
    _load(db_conn, make_files(GOOD_COLLISIONS, GOOD_VEHICLES, GOOD_CASUALTIES))
    bad_vehicles = [
        *GOOD_VEHICLES,
        {"collision_index": "1980A", "vehicle_reference": "3", "age_of_driver": "forty"},
    ]
    strict = Thresholds(max_quarantine_ratio=1.0, max_parse_failure_ratio=0.0, first_year=1979)

    with pytest.raises(ValidationFailed, match="parse_failures"):
        _load(db_conn, make_files(GOOD_COLLISIONS, bad_vehicles, GOOD_CASUALTIES), strict)

    assert _one(db_conn, "SELECT count(*) FROM core.vehicle") == (3,)
    status, message = _one(db_conn, "SELECT status, message FROM etl.run ORDER BY run_id DESC")
    assert status == "failed" and "parse_failures" in message
    detail = _one(
        db_conn,
        """SELECT detail FROM etl.run_check
                              WHERE check_name = 'parse_failures' AND table_name = 'vehicle'
                              ORDER BY run_id DESC""",
    )
    assert detail == ("age_of_driver=1",)


def test_row_count_drop_blocks_swap(db_conn, make_files):
    _load(db_conn, make_files(GOOD_COLLISIONS, GOOD_VEHICLES, GOOD_CASUALTIES))

    with pytest.raises(ValidationFailed, match="row_count_vs_previous"):
        _load(db_conn, make_files(GOOD_COLLISIONS[:2], GOOD_VEHICLES[:1], GOOD_CASUALTIES[:1]))

    assert _one(db_conn, "SELECT count(*) FROM core.collision") == (2,)


def test_year_gap_blocks_swap(db_conn, make_files):
    gap = [*GOOD_COLLISIONS, _collision("1982A", 1982)]

    with pytest.raises(ValidationFailed, match="year_coverage"):
        _load(db_conn, make_files(gap, GOOD_VEHICLES, GOOD_CASUALTIES))

    assert _one(db_conn, "SELECT count(*) FROM pg_namespace WHERE nspname = 'core'") == (0,)


# FU-008: two different casualties sharing a casualty_reference (seen 1991-94)
REUSED_REF_CASUALTIES = [
    *GOOD_CASUALTIES,
    {
        "collision_index": "1980A",
        "vehicle_reference": "2",
        "casualty_reference": "1",
        "age_of_casualty": "19",
    },
]


def test_reused_casualty_reference_is_kept_with_sequence(db_conn, make_files):
    _load(db_conn, make_files(GOOD_COLLISIONS, GOOD_VEHICLES, REUSED_REF_CASUALTIES))

    rows = db_conn.execute(
        """SELECT vehicle_reference, casualty_seq, is_reference_reused
           FROM core.casualty WHERE collision_index = '1980A' AND casualty_reference = 1
           ORDER BY casualty_seq"""
    ).fetchall()
    assert rows == [(1, 1, True), (2, 2, True)]
    assert _one(
        db_conn,
        """SELECT count(*) FROM core.quarantine
           WHERE table_name = 'casualty' AND reason = 'conflicting_duplicate_key'""",
    ) == (0,)


def test_normal_casualties_have_seq_one_and_no_flag(db_conn, make_files):
    _load(db_conn, make_files(GOOD_COLLISIONS, GOOD_VEHICLES, REUSED_REF_CASUALTIES))

    assert _one(
        db_conn,
        """SELECT casualty_seq, is_reference_reused FROM core.casualty
           WHERE collision_index = '1979A' AND casualty_reference = 1""",
    ) == (1, False)


def test_casualty_pk_includes_sequence(db_conn, make_files):
    _load(db_conn, make_files(GOOD_COLLISIONS, GOOD_VEHICLES, GOOD_CASUALTIES))

    cols = [
        r[0]
        for r in db_conn.execute(
            """SELECT a.attname FROM pg_index i
               JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
               WHERE i.indrelid = 'core.casualty'::regclass AND i.indisprimary
               ORDER BY array_position(i.indkey, a.attnum)"""
        )
    ]
    assert cols == ["collision_index", "casualty_reference", "casualty_seq"]


def test_reused_reference_reported_as_info_check(db_conn, make_files):
    run_id = _load(db_conn, make_files(GOOD_COLLISIONS, GOOD_VEHICLES, REUSED_REF_CASUALTIES))

    assert _one(
        db_conn,
        """SELECT severity, observed FROM etl.run_check
           WHERE run_id = %s AND check_name = 'casualty_reference_reused'""",
        (run_id,),
    ) == ("info", 2)


def test_supplement_labels_loaded_with_source(db_conn, make_files):
    _load(db_conn, make_files(GOOD_COLLISIONS, GOOD_VEHICLES, GOOD_CASUALTIES))

    assert _one(
        db_conn,
        """SELECT label, source FROM core.lookup_code
           WHERE table_name = 'casualty' AND field_name = 'casualty_type' AND code = '33'""",
    ) == ("Personal powered transporter (e.g. e-scooter) rider or passenger", "supplement")
    assert _one(
        db_conn,
        """SELECT source FROM core.lookup_code
           WHERE table_name = 'collision' AND field_name = 'light_conditions' AND code = '1'""",
    ) == ("dft_guide",)


def test_guide_field_unmatched_check_recorded(db_conn, make_files):
    run_id = _load(db_conn, make_files(GOOD_COLLISIONS, GOOD_VEHICLES, GOOD_CASUALTIES))

    assert _one(
        db_conn,
        """SELECT severity, passed, observed FROM etl.run_check
           WHERE run_id = %s AND check_name = 'guide_field_unmatched'""",
        (run_id,),
    ) == ("warn", True, 0)
