"""/api/hotspots: ranked cluster sites for a selection (PLAN-005).

The selection's points are fetched once (BNG metres); the greedy circle search runs
in Python (stats19.hotspots). Results are cached briefly, because the site list, the
site review and the site pack PDF all ask for the same run.
"""

from __future__ import annotations

import csv
import io
import json
import threading
import time
from collections import Counter
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from psycopg import sql
from pydantic import ValidationError

from stats19.api import cache
from stats19.api.deps import get_conn
from stats19.api.envelope import ApiError, ok
from stats19.api.filters import (
    Filter,
    collision_relation,
    compile_filter,
    count_capped,
    filter_param,
)
from stats19.api.prevention import prevention_values
from stats19.api.sites import worst_within
from stats19.hotspots import HotspotParams, Point, Site, find_sites

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Flt = Annotated[Filter, Depends(filter_param)]

# A county over five years is ~5-20k collisions; London over five years ~120k.
MAX_HOTSPOT_COLLISIONS = 100_000
CACHE_TTL_S = 15 * 60
CACHE_MAX = 32
LABEL_SEARCH_M = 25  # how far from a site centre to look for a named road

_ROAD_PREFIX = {1: "M", 2: "A", 3: "A", 4: "B"}  # 2 = A(M)


def parse_params(p: str | None) -> HotspotParams:
    if not p:
        return HotspotParams()
    try:
        return HotspotParams.model_validate_json(p)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


def params_param(p: Annotated[str | None, Query(max_length=2000)] = None) -> HotspotParams:
    return parse_params(p)


Params = Annotated[HotspotParams, Depends(params_param)]


def road_ref(road_class: int | None, number: int | None) -> str | None:
    """'A38', 'A1(M)', 'M5', 'B3212'; None for C / unclassified / unknown roads."""
    if road_class not in _ROAD_PREFIX or not number or number <= 0:
        return None
    return f"{_ROAD_PREFIX[road_class]}{number}{'(M)' if road_class == 2 else ''}"


def _points_sql(rel: sql.Composable, where: sql.Composable) -> sql.Composable:
    return sql.SQL(
        """SELECT c.collision_index AS id, ST_X(c.geom_bng) AS x, ST_Y(c.geom_bng) AS y,
                  ST_X(c.geom_wgs84) AS lon, ST_Y(c.geom_wgs84) AS lat,
                  c.collision_severity AS severity, c.urban_or_rural_area = 2 AS rural,
                  c.collision_adjusted_severity_serious AS adj_serious,
                  c.collision_year AS year, c.junction_detail,
                  c.first_road_class, c.first_road_number,
                  c.second_road_class, c.second_road_number
           FROM {rel} c
           WHERE {where} AND c.geom_bng IS NOT NULL AND c.collision_severity IN (1, 2, 3)"""
    ).format(rel=rel, where=where)


def _p_ksi(row: dict) -> float | None:
    """DfT's adjusted probability that the collision is KSI (FU-047 #10)."""
    if row["severity"] == 1:
        return 1.0
    return None if row["adj_serious"] is None else float(row["adj_serious"])


def _expected_value(row: dict, values: dict[int, float]) -> float:
    """Value of prevention on the adjusted severity: serious with its probability."""
    p = _p_ksi(row)
    if row["severity"] == 1 or p is None:
        return values[row["severity"]]
    return p * values[2] + (1 - p) * values[3]


def _site_roads(rows: list[dict]) -> list[str]:
    """Most common numbered roads at the site (the second road only at junctions)."""
    counts: Counter[str] = Counter()
    for r in rows:
        refs = {road_ref(r["first_road_class"], r["first_road_number"])}
        if r["junction_detail"] not in (None, -1, 0, 99):
            refs.add(road_ref(r["second_road_class"], r["second_road_number"]))
        counts.update(ref for ref in refs if ref)
    return [ref for ref, n in counts.most_common(2) if n * 4 >= len(rows)]  # >= 25% of the site


def _nearby_roads(conn: psycopg.Connection, sites: list[Site]) -> dict[int, dict]:
    if not sites:
        return {}
    rows = conn.execute(
        """SELECT s.i, r.name, r.town
           FROM unnest(%(xs)s::float8[], %(ys)s::float8[]) WITH ORDINALITY AS s(x, y, i)
           CROSS JOIN LATERAL (
               SELECT p.name, coalesce(p.populated_place, p.district) AS town
               FROM geo.place p
               WHERE p.local_type = 'Named Road'
                 AND ST_DWithin(p.bbox_bng, ST_SetSRID(ST_MakePoint(s.x, s.y), 27700), %(d)s)
               ORDER BY ST_Distance(p.geom_bng, ST_SetSRID(ST_MakePoint(s.x, s.y), 27700))
               LIMIT 1) r""",
        {"xs": [s.cx for s in sites], "ys": [s.cy for s in sites], "d": LABEL_SEARCH_M},
    ).fetchall()
    return {r["i"]: {"name": r["name"], "town": r["town"]} for r in rows}


def _label(roads: list[str], near: dict | None) -> str:
    parts = [" / ".join(roads)] if roads else []
    if near:
        parts.append(f"near {near['name']}" + (f", {near['town']}" if near["town"] else ""))
    return ", ".join(parts) or "Unclassified road"


def _site_json(site: Site, rows: dict[str, dict], near: dict | None, years: range) -> dict:
    member_rows = [rows[p.id] for p in site.members]
    roads = _site_roads(member_rows)
    by_year = Counter(p.year for p in site.members)
    ksi_by_year = Counter(p.year for p in site.members if p.severity in (1, 2))
    centre = rows[site.centre.id]
    return {
        "rank": site.rank,
        "label": _label(roads, near),
        "roads": roads,
        "near": near,
        "lon": centre["lon"],
        "lat": centre["lat"],
        "radius_m": site.radius_m,
        "collisions": site.collisions,
        "fatal": site.fatal,
        "serious": site.serious,
        "slight": site.slight,
        "ksi": site.ksi,
        "score": round(site.score, 2),
        "value_of_prevention": round(sum(p.value for p in site.members)),
        "by_year": [{"year": y, "n": by_year[y], "ksi": ksi_by_year[y]} for y in years],
        "collision_ids": sorted(p.id for p in site.members),
    }


def run_hotspots(conn: psycopg.Connection, flt: Filter, params: HotspotParams) -> dict:
    total = count_capped(conn, flt, MAX_HOTSPOT_COLLISIONS)
    if total > MAX_HOTSPOT_COLLISIONS:
        raise ApiError(
            413,
            "too_large",
            f"Hotspot analysis covers up to {MAX_HOTSPOT_COLLISIONS:,} collisions. "
            "Choose an authority or area, or a shorter period.",
        )
    price_year, values = prevention_values(conn)
    where, qp = compile_filter(flt)
    rows = conn.execute(_points_sql(collision_relation(flt), where), qp).fetchall()
    points = [
        Point(
            id=r["id"],
            x=r["x"],
            y=r["y"],
            severity=r["severity"],
            rural=bool(r["rural"]),
            year=r["year"],
            value=_expected_value(r, values),
            p_ksi=_p_ksi(r),
        )
        for r in rows
    ]
    sites = find_sites(points, params)
    near = _nearby_roads(conn, sites)
    by_id = {r["id"]: r for r in rows}
    found_years = [p.year for p in points]
    years = range(
        flt.year_from or min(found_years, default=0),
        (flt.year_to or max(found_years, default=-1)) + 1,
    )
    return {
        "params": params.model_dump(),
        "selection": {"collisions": total, "located": len(points)},
        "value_price_year": price_year,
        "sites": [_site_json(s, by_id, near.get(i + 1), years) for i, s in enumerate(sites)],
    }


class _Cache:
    """Small in-process TTL cache keyed on the canonical filter + parameters."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, tuple[float, dict]] = {}

    def get(self, key: str) -> dict | None:
        with self._lock:
            hit = self._items.get(key)
            if hit and time.monotonic() - hit[0] < CACHE_TTL_S:
                return hit[1]
            self._items.pop(key, None)
            return None

    def put(self, key: str, value: dict) -> None:
        with self._lock:
            if len(self._items) >= CACHE_MAX:
                oldest = min(self._items, key=lambda k: self._items[k][0])
                del self._items[oldest]
            self._items[key] = (time.monotonic(), value)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


CACHE = _Cache()


def cached_hotspots(conn: psycopg.Connection, flt: Filter, params: HotspotParams) -> dict:
    load = cache.data_load(conn)
    key = f"{load}|{flt.model_dump_json()}|{params.model_dump_json()}"
    result = CACHE.get(key)
    if result is None:
        result = {**run_hotspots(conn, flt, params), "data_load": load}
        CACHE.put(key, result)
    return result


CSV_COLUMNS = (
    "rank",
    "label",
    "lon",
    "lat",
    "radius_m",
    "collisions",
    "fatal",
    "serious",
    "slight",
    "ksi",
    "score",
    "value_of_prevention",
    "collision_ids",
)


def _cell(value: object) -> object:
    """Text that a spreadsheet would run as a formula is prefixed with a quote."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def sites_csv(result: dict) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for s in result["sites"]:
        writer.writerow(
            [_cell(";".join(s[c]) if c == "collision_ids" else s[c]) for c in CSV_COLUMNS]
        )
    return out.getvalue()


@router.get("/hotspots")
def hotspots(conn: Conn, flt: Flt, params: Params) -> dict:
    result = cached_hotspots(conn, flt, params)
    # the safety model rebuilds on its own schedule, so this isn't cached with the sites
    worst = worst_within(conn, result["sites"])
    return ok(result | {"sites": [s | {"worse": worst.get(s["rank"])} for s in result["sites"]]})


@router.get("/hotspots.csv")
def hotspots_csv(conn: Conn, flt: Flt, params: Params) -> Response:
    body = sites_csv(cached_hotspots(conn, flt, params))
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="stats19-cluster-sites.csv"'},
    )


CIRCLE_SEGMENTS = 16  # per quarter circle: smooth at site scale, small files

_CIRCLES = f"""
SELECT s.rank,
       ST_AsGeoJSON(ST_Transform(ST_Buffer(
           ST_Transform(ST_SetSRID(ST_MakePoint(s.lon, s.lat), 4326), 27700),
           s.radius, {CIRCLE_SEGMENTS}), 4326), 6)::json AS geometry
FROM unnest(%(ranks)s::int[], %(lons)s::float8[], %(lats)s::float8[], %(radii)s::float8[])
     AS s(rank, lon, lat, radius)
"""


def sites_geojson(conn: psycopg.Connection, result: dict) -> dict:
    """Cluster sites as true-radius circles (drawn in British National Grid) for GIS."""
    sites = result["sites"]
    rows = conn.execute(
        _CIRCLES,
        {
            "ranks": [s["rank"] for s in sites],
            "lons": [s["lon"] for s in sites],
            "lats": [s["lat"] for s in sites],
            "radii": [float(s["radius_m"]) for s in sites],
        },
    ).fetchall()
    circles = {}
    for row in rows:  # positional: works with tuple and dict row factories
        rank, geometry = row.values() if isinstance(row, dict) else row
        circles[rank] = geometry
    props = [c for c in CSV_COLUMNS if c != "collision_ids"]
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": circles[s["rank"]],
                "properties": {c: s[c] for c in props}
                | {"collision_ids": ";".join(s["collision_ids"])},
            }
            for s in sites
        ],
    }


@router.get("/hotspots.geojson")
def hotspots_geojson(conn: Conn, flt: Flt, params: Params) -> Response:
    body = json.dumps(sites_geojson(conn, cached_hotspots(conn, flt, params)))
    return Response(
        content=body,
        media_type="application/geo+json",
        headers={"Content-Disposition": 'attachment; filename="stats19-cluster-sites.geojson"'},
    )
