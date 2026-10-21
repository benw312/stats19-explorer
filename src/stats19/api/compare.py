"""/api/compare: what is over-represented in a selection (e.g. a cluster site) compared
with a base selection (e.g. the authority it sits in). PLAN-005 §3.

Every indicator is a recorded field, or a simple combination of recorded fields;
there are no derived collision types (FU-001). Collisions whose value is unknown are
left out of both the count and the denominator for that indicator.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Query
from psycopg import sql

from stats19.api import cache
from stats19.api.deps import get_conn
from stats19.api.envelope import ApiError, ok
from stats19.api.filters import Filter, compile_filter, count_capped, parse_filter
from stats19.hotspots import binomial_sf

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]

MAX_COMPARE_SELECTION = 5_000
MAX_COMPARE_BASE = 200_000  # same as the summary cap
NOTABLE_P = 0.05
NOTABLE_MIN_COUNT = 2


@dataclass(frozen=True)
class Indicator:
    key: str
    group: str
    label: str
    hit: str  # SQL over mart.collision c: true when the indicator applies
    known: str = "TRUE"  # SQL: the value is recorded, so the collision counts at all


def _vehicle(cond: str) -> str:
    return (
        "EXISTS (SELECT 1 FROM core.vehicle v "
        f"WHERE v.collision_index = c.collision_index AND {cond})"
    )


_HOUR = "extract(hour FROM c.collision_time)"

INDICATORS: tuple[Indicator, ...] = (
    Indicator("ksi", "Severity", "Killed or seriously injured", "c.collision_severity IN (1, 2)"),
    Indicator(
        "dark",
        "Light",
        "Dark",
        "c.light_conditions BETWEEN 4 AND 7",
        "c.light_conditions BETWEEN 1 AND 7",
    ),
    Indicator(
        "dark_unlit",
        "Light",
        "Dark, street lights unlit or none",
        "c.light_conditions IN (5, 6)",
        "c.light_conditions IN (1, 4, 5, 6)",
    ),
    Indicator(
        "wet",
        "Surface",
        "Wet or damp road",
        "c.road_surface_conditions = 2",
        "c.road_surface_conditions BETWEEN 1 AND 7",
    ),
    Indicator(
        "icy",
        "Surface",
        "Snow, frost or ice on road",
        "c.road_surface_conditions IN (3, 4)",
        "c.road_surface_conditions BETWEEN 1 AND 7",
    ),
    Indicator(
        "rain_snow_fog",
        "Weather",
        "Raining, snowing or fog",
        "c.weather_conditions IN (2, 3, 5, 6, 7)",
        "c.weather_conditions BETWEEN 1 AND 8",
    ),
    Indicator(
        "high_winds",
        "Weather",
        "High winds",
        "c.weather_conditions IN (4, 5, 6)",
        "c.weather_conditions BETWEEN 1 AND 8",
    ),
    Indicator(
        "junction",
        "Location",
        "At a junction (other than a roundabout)",
        "c.junction_detail IN (13, 16, 17, 18, 19)",
        "c.junction_detail IN (0, 13, 16, 17, 18, 19)",
    ),
    Indicator(
        "roundabout",
        "Location",
        "Roundabout",
        "c.road_type = 1",
        "c.road_type IN (1, 2, 3, 6, 7, 12)",
    ),
    Indicator(
        "weekend", "Time", "Weekend", "c.day_of_week IN (1, 7)", "c.day_of_week BETWEEN 1 AND 7"
    ),
    Indicator(
        "am_peak",
        "Time",
        "Morning peak (07:00–09:59)",
        f"{_HOUR} BETWEEN 7 AND 9",
        "c.collision_time IS NOT NULL",
    ),
    Indicator(
        "pm_peak",
        "Time",
        "Evening peak (16:00–18:59)",
        f"{_HOUR} BETWEEN 16 AND 18",
        "c.collision_time IS NOT NULL",
    ),
    Indicator(
        "night",
        "Time",
        "Night (22:00–05:59)",
        f"({_HOUR} >= 22 OR {_HOUR} < 6)",
        "c.collision_time IS NOT NULL",
    ),
    Indicator("pedestrian", "Road users", "Pedestrian casualty", "c.has_pedestrian_casualty"),
    Indicator("pedal_cycle", "Road users", "Pedal cycle involved", "c.involves_pedal_cycle"),
    Indicator("motorcycle", "Road users", "Motorcycle involved", "c.involves_motorcycle"),
    Indicator("goods_heavy", "Road users", "HGV involved", "c.involves_goods_heavy"),
    Indicator("single_vehicle", "Vehicles", "Single-vehicle collision", "c.number_of_vehicles = 1"),
    Indicator(
        "turning_right",
        "Vehicles",
        "A vehicle turning or waiting to turn right",
        _vehicle("v.vehicle_manoeuvre IN (9, 10)"),
    ),
    Indicator(
        "turning_left",
        "Vehicles",
        "A vehicle turning or waiting to turn left",
        _vehicle("v.vehicle_manoeuvre IN (7, 8)"),
    ),
    Indicator(
        "slowing",
        "Vehicles",
        "A vehicle slowing, stopping or waiting",
        _vehicle("v.vehicle_manoeuvre IN (3, 4)"),
    ),
    Indicator(
        "skid",
        "Vehicles",
        "A vehicle skidded, jack-knifed or overturned",
        _vehicle("v.skidding_and_overturning BETWEEN 1 AND 5"),
    ),
    Indicator(
        "left_carriageway",
        "Vehicles",
        "A vehicle left the carriageway",
        _vehicle("v.vehicle_leaving_carriageway BETWEEN 1 AND 8"),
    ),
    Indicator(
        "young_driver",
        "People",
        "Driver aged 17–24",
        "c.youngest_driver_age BETWEEN 17 AND 24",
        "c.youngest_driver_age > 0",
    ),
    Indicator(
        "older_driver",
        "People",
        "Driver aged 70 or over",
        "c.oldest_driver_age >= 70",
        "c.oldest_driver_age > 0",
    ),
    Indicator(
        "child_casualty",
        "People",
        "Child casualty (under 16)",
        "EXISTS (SELECT 1 FROM core.casualty k WHERE k.collision_index = c.collision_index "
        "AND k.age_of_casualty BETWEEN 0 AND 15)",
    ),
)


def _counts_sql(where: sql.Composable) -> sql.Composable:
    # Indicator SQL is a module constant, never client input.
    flags = ",\n".join(f"CASE WHEN {i.known} THEN ({i.hit}) END AS {i.key}" for i in INDICATORS)
    aggs = ",\n".join(
        f"count(*) FILTER (WHERE {i.key}) AS {i.key}_n, count({i.key}) AS {i.key}_of"
        for i in INDICATORS
    )
    return sql.SQL(
        "WITH s AS MATERIALIZED (SELECT " + flags + " FROM mart.collision c WHERE {where}) "
        "SELECT count(*) AS total, " + aggs + " FROM s"
    ).format(where=where)


def indicator_counts(conn: psycopg.Connection, f: Filter) -> dict:
    where, params = compile_filter(f)
    return conn.execute(_counts_sql(where), params).fetchone()


# The area baseline is the same for every site in a run (e.g. 25 sites in a pack).
_BASE_CACHE: OrderedDict[str, dict] = OrderedDict()
_BASE_CACHE_MAX = 64
_base_lock = threading.Lock()


def base_counts(conn: psycopg.Connection, f: Filter) -> dict:
    key = f"{cache.data_load(conn)}|{f.model_dump_json()}"
    with _base_lock:
        if key in _BASE_CACHE:
            _BASE_CACHE.move_to_end(key)
            return _BASE_CACHE[key]
    counts = indicator_counts(conn, f)
    with _base_lock:
        _BASE_CACHE[key] = counts
        while len(_BASE_CACHE) > _BASE_CACHE_MAX:
            _BASE_CACHE.popitem(last=False)
    return counts


def clear_base_cache() -> None:
    with _base_lock:
        _BASE_CACHE.clear()


def compare(selection: dict, base: dict) -> list[dict]:
    out = []
    for i in INDICATORS:
        n, of = selection[f"{i.key}_n"], selection[f"{i.key}_of"]
        bn, bof = base[f"{i.key}_n"], base[f"{i.key}_of"]
        share = n / of if of else None
        base_share = bn / bof if bof else None
        p = binomial_sf(n, of, base_share) if of and base_share is not None else None
        out.append(
            {
                "key": i.key,
                "group": i.group,
                "label": i.label,
                "n": n,
                "of": of,
                "share": share,
                "base_n": bn,
                "base_of": bof,
                "base_share": base_share,
                "ratio": share / base_share if share is not None and base_share else None,
                "p": p,
                "notable": bool(
                    p is not None
                    and p < NOTABLE_P
                    and n >= NOTABLE_MIN_COUNT
                    and share is not None
                    and base_share is not None
                    and share > base_share
                ),
            }
        )
    return out


def _too_large(what: str, cap: int) -> ApiError:
    return ApiError(
        413, "too_large", f"The {what} for a comparison is limited to {cap:,} collisions."
    )


@router.get("/compare")
def compare_route(
    conn: Conn,
    f: Annotated[str | None, Query(max_length=20_000)] = None,
    base: Annotated[str | None, Query(max_length=20_000)] = None,
) -> dict:
    selection_f, base_f = parse_filter(f), parse_filter(base)
    if count_capped(conn, selection_f, MAX_COMPARE_SELECTION) > MAX_COMPARE_SELECTION:
        raise _too_large("selection", MAX_COMPARE_SELECTION)
    if count_capped(conn, base_f, MAX_COMPARE_BASE) > MAX_COMPARE_BASE:
        raise _too_large("comparison area", MAX_COMPARE_BASE)
    sel, bas = indicator_counts(conn, selection_f), base_counts(conn, base_f)
    return ok(
        {
            "collisions": sel["total"],
            "base_collisions": bas["total"],
            "indicators": compare(sel, bas),
        }
    )
