"""Column specification for the three STATS19 tables.

This is the single source of truth for expected CSV headers and their target
Postgres types. Raw tables are loaded as TEXT exactly as published; the typed
SELECT generated here converts them using the SQL helpers in
``sql/migrations/001_etl.sql``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class Kind(Enum):
    """How a raw text column is converted (see _KIND_SQL for type + template)."""

    KEY_TEXT = "key_text"
    KEY_INT = "key_int"
    TEXT = "text"
    # Coded categorical value; -1 ("data missing or out of range") is kept as it has a label.
    CODE = "code"
    # Non-negative count; kept as published.
    COUNT = "count"
    # Continuous measure; -1 sentinel becomes NULL.
    MEASURE = "measure"
    FLOAT = "float"
    DATE = "date"
    TIME = "time"

    @property
    def sql_type(self) -> str:
        return _KIND_SQL[self][0]

    def convert(self, column: str) -> str:
        return _KIND_SQL[self][1].format(c=column)


_TEXT_SQL = "NULLIF(btrim(r.{c}), '')"
_KIND_SQL: dict[Kind, tuple[str, str]] = {
    Kind.KEY_TEXT: ("text", _TEXT_SQL),
    Kind.KEY_INT: ("smallint", "etl.to_code(r.{c})"),
    Kind.TEXT: ("text", _TEXT_SQL),
    Kind.CODE: ("smallint", "etl.to_code(r.{c})"),
    Kind.COUNT: ("integer", "etl.to_int(r.{c})"),
    Kind.MEASURE: ("integer", "etl.to_measure(r.{c})"),
    Kind.FLOAT: ("double precision", "etl.to_float(r.{c})"),
    Kind.DATE: ("date", "etl.to_date_dmy(r.{c})"),
    Kind.TIME: ("time", "etl.to_hhmm(r.{c})"),
}


@dataclass(frozen=True)
class Column:
    name: str
    kind: Kind
    optional: bool = False


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[Column, ...]
    primary_key: tuple[str, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)


@dataclass(frozen=True)
class HeaderCheck:
    missing: list[str]
    unexpected: list[str]


class HeaderError(ValueError):
    """Raised when a source file lacks required columns."""


K = Kind


def _cols(*items: tuple[str, Kind] | tuple[str, Kind, bool]) -> tuple[Column, ...]:
    return tuple(Column(*item) for item in items)


_KEYS = (
    ("collision_index", K.KEY_TEXT),
    ("collision_year", K.KEY_INT),
    ("collision_ref_no", K.TEXT),
)

COLLISION = TableSpec(
    name="collision",
    primary_key=("collision_index",),
    columns=_cols(
        *_KEYS,
        ("location_easting_osgr", K.MEASURE),
        ("location_northing_osgr", K.MEASURE),
        ("longitude", K.FLOAT),
        ("latitude", K.FLOAT),
        ("police_force", K.CODE),
        ("collision_severity", K.CODE),
        ("number_of_vehicles", K.COUNT),
        ("number_of_casualties", K.COUNT),
        ("date", K.DATE),
        ("day_of_week", K.CODE),
        ("time", K.TIME),
        ("local_authority_district", K.CODE),
        ("local_authority_ons_district", K.TEXT),
        ("local_authority_highway", K.TEXT),
        ("local_authority_highway_current", K.TEXT, True),
        ("first_road_class", K.CODE),
        ("first_road_number", K.MEASURE),
        ("road_type", K.CODE),
        # mph value, not a category: the guide only labels -1 (missing) and 99 (unknown).
        ("speed_limit", K.MEASURE),
        ("junction_detail_historic", K.CODE, True),
        ("junction_detail", K.CODE),
        ("junction_control", K.CODE),
        ("second_road_class", K.CODE),
        ("second_road_number", K.MEASURE),
        ("pedestrian_crossing_human_control_historic", K.CODE, True),
        ("pedestrian_crossing_physical_facilities_historic", K.CODE, True),
        ("pedestrian_crossing", K.CODE, True),
        ("light_conditions", K.CODE),
        ("weather_conditions", K.CODE),
        ("road_surface_conditions", K.CODE),
        ("special_conditions_at_site", K.CODE),
        ("carriageway_hazards_historic", K.CODE, True),
        ("carriageway_hazards", K.CODE),
        ("urban_or_rural_area", K.CODE),
        ("did_police_officer_attend_scene_of_accident", K.CODE),
        ("trunk_road_flag", K.CODE),
        ("lsoa_of_accident_location", K.TEXT),
        ("enhanced_severity_collision", K.CODE, True),
        ("collision_injury_based", K.CODE, True),
        ("collision_adjusted_severity_serious", K.FLOAT, True),
        ("collision_adjusted_severity_slight", K.FLOAT, True),
    ),
)

VEHICLE = TableSpec(
    name="vehicle",
    primary_key=("collision_index", "vehicle_reference"),
    columns=_cols(
        *_KEYS,
        ("vehicle_reference", K.KEY_INT),
        ("vehicle_type", K.CODE),
        ("towing_and_articulation", K.CODE),
        ("vehicle_manoeuvre_historic", K.CODE, True),
        ("vehicle_manoeuvre", K.CODE),
        ("vehicle_direction_from", K.CODE),
        ("vehicle_direction_to", K.CODE),
        ("vehicle_location_restricted_lane_historic", K.CODE, True),
        ("vehicle_location_restricted_lane", K.CODE),
        ("junction_location", K.CODE),
        ("skidding_and_overturning", K.CODE),
        ("hit_object_in_carriageway", K.CODE),
        ("vehicle_leaving_carriageway", K.CODE),
        ("hit_object_off_carriageway", K.CODE),
        ("first_point_of_impact", K.CODE),
        ("vehicle_left_hand_drive", K.CODE),
        ("journey_purpose_of_driver_historic", K.CODE, True),
        ("journey_purpose_of_driver", K.CODE),
        ("sex_of_driver", K.CODE),
        ("age_of_driver", K.MEASURE),
        ("age_band_of_driver", K.CODE),
        ("engine_capacity_cc", K.MEASURE),
        ("propulsion_code", K.CODE),
        ("age_of_vehicle", K.MEASURE),
        ("generic_make_model", K.TEXT),
        ("driver_imd_decile", K.CODE),
        ("lsoa_of_driver", K.TEXT),
        ("escooter_flag", K.CODE, True),
        ("driver_distance_banding", K.CODE, True),
    ),
)

CASUALTY = TableSpec(
    name="casualty",
    primary_key=("collision_index", "casualty_reference"),
    columns=_cols(
        *_KEYS,
        ("vehicle_reference", K.KEY_INT),
        ("casualty_reference", K.KEY_INT),
        ("casualty_class", K.CODE),
        ("sex_of_casualty", K.CODE),
        ("age_of_casualty", K.MEASURE),
        ("age_band_of_casualty", K.CODE),
        ("casualty_severity", K.CODE),
        ("pedestrian_location", K.CODE),
        ("pedestrian_movement", K.CODE),
        ("car_passenger", K.CODE),
        ("bus_or_coach_passenger", K.CODE),
        ("pedestrian_road_maintenance_worker", K.CODE),
        ("casualty_type", K.CODE),
        ("casualty_imd_decile", K.CODE),
        ("lsoa_of_casualty", K.TEXT),
        ("enhanced_casualty_severity", K.CODE, True),
        ("casualty_injury_based", K.CODE, True),
        ("casualty_adjusted_severity_serious", K.FLOAT, True),
        ("casualty_adjusted_severity_slight", K.FLOAT, True),
        ("casualty_distance_banding", K.CODE, True),
        ("escooter_flag", K.CODE, True),
    ),
)

TABLES: dict[str, TableSpec] = {t.name: t for t in (COLLISION, VEHICLE, CASUALTY)}

# Columns renamed in core (see sql/build/core.sql): bare "date"/"time" are awkward to query.
CORE_RENAMES: dict[tuple[str, str], str] = {
    ("collision", "date"): "collision_date",
    ("collision", "time"): "collision_time",
}


def core_name(table: str, column: str) -> str:
    return CORE_RENAMES.get((table, column), column)


# Pre-2024 releases used "accident" naming for the key columns.
LEGACY_RENAMES: dict[str, str] = {
    "accident_index": "collision_index",
    "accident_year": "collision_year",
    "accident_reference": "collision_ref_no",
    "accident_severity": "collision_severity",
}


def unmatched_guide_fields(pairs: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """Guide (table, field) pairs for our three tables with no matching spec column.

    The guide also documents other datasets (e.g. historical_revisions); those are ignored.
    """
    return sorted(
        (table, field)
        for table, field in pairs
        if table in TABLES and field not in TABLES[table].names
    )


def normalise_header(header: Iterable[str]) -> list[str]:
    """Lower-case, trim, drop a UTF-8 BOM and apply legacy renames."""
    cleaned = (h.replace("﻿", "").strip().lower() for h in header)
    return [LEGACY_RENAMES.get(h, h) for h in cleaned]


def check_header(spec: TableSpec, header: Iterable[str]) -> HeaderCheck:
    """Compare a normalised header with the spec; raise if required columns are missing."""
    present = list(header)
    present_set = set(present)
    missing = [c for c in spec.columns if c.name not in present_set]
    required_missing = [c.name for c in missing if not c.optional]
    if required_missing:
        raise HeaderError(f"{spec.name}: missing required columns {required_missing}")
    expected = set(spec.names)
    return HeaderCheck(
        missing=[c.name for c in missing],
        unexpected=[h for h in present if h not in expected],
    )


def parse_failure_exprs(spec: TableSpec, available: set[str]) -> list[tuple[str, str]]:
    """(column, SQL boolean) pairs true when a raw value is non-blank but unparseable.

    Text columns can't fail so they are skipped. Measures are tested with the plain
    integer parser so that a legitimate -1 isn't counted as a failure.
    """
    out = []
    for c in spec.columns:
        if c.name not in available or c.kind in (Kind.TEXT, Kind.KEY_TEXT):
            continue
        kind = Kind.COUNT if c.kind is Kind.MEASURE else c.kind
        out.append((c.name, f"(btrim(r.{c.name}) <> '' AND {kind.convert(c.name)} IS NULL)"))
    return out


def typed_select_list(spec: TableSpec, available: set[str]) -> str:
    """SELECT-list converting raw text columns (aliased ``r``) to typed columns."""
    exprs = [
        f"{c.kind.convert(c.name)} AS {c.name}"
        if c.name in available
        else f"NULL::{c.kind.sql_type} AS {c.name}"
        for c in spec.columns
    ]
    return ",\n    ".join(exprs)
