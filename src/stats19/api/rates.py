"""/api/rates: casualty rates for an authority against similar authorities (PLAN-009 §10).

Numerator: casualties in the collisions that match the filter, counted per authority with
STATS19's own highway authority field (DfT's published authority figures). Casualty-level
choices narrow it further: chosen road users count only their own casualties ("pedestrian
casualties"), a chosen severity counts casualties of that severity, and casualty field
conditions apply to each casualty. Major/minor follows the police first road class.

Denominators come from geo.authority_year (population, vehicle-km, road length). Only a
highway authority has them all; any other area gets the major-road rate from the count
points inside it.
"""

from __future__ import annotations

import threading
from collections import OrderedDict, defaultdict
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends
from psycopg import sql

from stats19.api import cache
from stats19.api import rate_calc as rc
from stats19.api.deps import get_conn
from stats19.api.envelope import NotFound, ok
from stats19.api.filters import (
    AuthorityArea,
    Filter,
    _condition,
    collision_relation,
    compile_filter,
    filter_param,
)
from stats19.api.traffic import major_vehicle_km
from stats19.reference.swap import tables_exist

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Flt = Annotated[Filter, Depends(filter_param)]

DEFAULT_YEARS = 5
_MAJOR, _MINOR = (1, 2, 3), (4, 5, 6)  # first_road_class: M, A(M), A | B, C, U

_COUNTS = """
SELECT {group} AS code, c.collision_year AS year,
       count(*) FILTER (WHERE c.first_road_class = ANY(%(major)s)) AS major,
       count(*) FILTER (WHERE c.first_road_class = ANY(%(minor)s)) AS minor,
       count(*) FILTER (WHERE NOT c.first_road_class = ANY(%(major)s || %(minor)s)) AS other,
       -- KSI on DfT's adjusted severity: forces record serious injuries differently
       -- (CRASH), so raw KSI isn't comparable between authorities (FU-047 #3)
       sum(CASE WHEN k.casualty_severity = 1 THEN 1.0
                ELSE coalesce(k.casualty_adjusted_severity_serious,
                              (k.casualty_severity = 2)::int) END) AS ksi
FROM {rel} c
JOIN core.casualty k ON k.collision_index = c.collision_index
{groups}
WHERE {where}
GROUP BY 1, 2
"""

_DENOMINATORS = """
SELECT code, year, population, vehicle_km, major_vehicle_km, minor_vehicle_km, road_km,
       recording_gap
FROM geo.authority_year WHERE year BETWEEN %(y0)s AND %(y1)s
"""


def rates_available(conn: psycopg.Connection) -> bool:
    return tables_exist(conn, "geo.authority", "geo.authority_year", "geo.authority_peer")


def period(conn: psycopg.Connection, flt: Filter) -> tuple[int, int]:
    """The filter's years, else the latest DEFAULT_YEARS."""
    latest = conn.execute("SELECT max(collision_year) AS y FROM core.collision").fetchone()["y"]
    y1 = min(flt.year_to or latest, latest)
    return flt.year_from or y1 - DEFAULT_YEARS + 1, y1


def _casualty_narrowing(flt: Filter) -> tuple[list[sql.Composable], dict, bool]:
    """Casualty-level conditions on k (core.casualty); whether road user groups are joined."""
    parts: list[sql.Composable] = []
    params: dict = {}
    if flt.involves:
        parts.append(sql.SQL("g.road_user_group = ANY(%(rate_groups)s)"))
        params["rate_groups"] = list(flt.involves)
    if flt.severity:
        parts.append(sql.SQL("k.casualty_severity = ANY(%(rate_severity)s)"))
        params["rate_severity"] = list(flt.severity)
    for i, cond in enumerate(flt.fields):
        if cond.table == "casualty":
            expr, p = _condition(100 + i, cond, "k")
            parts.append(expr)
            params.update(p)
    return parts, params, bool(flt.involves)


# Counts for every authority don't depend on which one is selected: switching to a peer, or
# back, reuses them. Keyed by the latest data load, so a new release is never served stale.
_COUNT_CACHE: OrderedDict[str, dict] = OrderedDict()
_COUNT_CACHE_MAX = 32
_count_lock = threading.Lock()


def authority_counts(conn: psycopg.Connection, flt: Filter) -> dict[str, dict[int, rc.Counts]]:
    """Casualties for every authority and year, for the filter without its area (cached)."""
    flt = flt.model_copy(update={"area": None})
    key = f"{cache.data_load(conn)}|{flt.model_dump_json()}"
    with _count_lock:
        if key in _COUNT_CACHE:
            _COUNT_CACHE.move_to_end(key)
            return _COUNT_CACHE[key]
    counts = count_casualties(conn, flt, by_authority=True)
    with _count_lock:
        _COUNT_CACHE[key] = counts
        while len(_COUNT_CACHE) > _COUNT_CACHE_MAX:
            _COUNT_CACHE.popitem(last=False)
    return counts


def clear_count_cache() -> None:
    with _count_lock:
        _COUNT_CACHE.clear()


def count_casualties(
    conn: psycopg.Connection, flt: Filter, by_authority: bool
) -> dict[str, dict[int, rc.Counts]]:
    """Casualties by authority (or one group, '') and year, for the filter."""
    narrowing, extra_params, join_groups = _casualty_narrowing(flt)
    where, params = compile_filter(flt, narrowing)
    query = sql.SQL(_COUNTS).format(
        group=sql.SQL("c.local_authority_highway_current" if by_authority else "''"),
        rel=collision_relation(flt),
        groups=sql.SQL(
            "JOIN mart.road_user_group g ON g.code = k.casualty_type" if join_groups else ""
        ),
        where=where,
    )
    rows = conn.execute(
        query, params | extra_params | {"major": list(_MAJOR), "minor": list(_MINOR)}
    ).fetchall()
    out: dict[str, dict[int, rc.Counts]] = defaultdict(dict)
    for r in rows:
        out[r["code"]][r["year"]] = rc.Counts(
            r["major"], r["minor"], r["other"], float(r["ksi"] or 0)
        )
    return out


Denoms = dict[str, dict[int, rc.Denominators]]


def _denominators(
    conn: psycopg.Connection, y0: int, y1: int
) -> tuple[Denoms, Denoms, dict[str, dict[int, float]]]:
    """(trusted, every year, recording gaps): trusted leaves out each authority's years with
    a possible recording gap, so no pooled rate (its own, peers', region, GB) includes them."""
    every: Denoms = defaultdict(dict)
    gaps: dict[str, dict[int, float]] = defaultdict(dict)
    for r in conn.execute(_DENOMINATORS, {"y0": y0, "y1": y1}):
        every[r["code"]][r["year"]] = rc.Denominators(
            r["population"],
            r["vehicle_km"],
            r["major_vehicle_km"],
            r["minor_vehicle_km"],
            r["road_km"],
        )
        if r["recording_gap"] is not None:
            gaps[r["code"]][r["year"]] = r["recording_gap"]
    trusted: Denoms = {
        c: {y: d for y, d in years.items() if y not in gaps.get(c, {})}
        for c, years in every.items()
    }
    return trusted, every, gaps


def _rate_json(rates: dict[str, rc.Rate]) -> dict:
    return {
        name: {"value": r.value, "count": r.count, "low": r.low, "high": r.high}
        for name, r in rates.items()
    }


def _values(rates: dict[str, rc.Rate]) -> dict[str, float | None]:
    return {name: r.value for name, r in rates.items()}


def _spread(summary: tuple[float, float, float] | None) -> dict | None:
    return None if summary is None else dict(zip(("median", "q1", "q3"), summary, strict=True))


_AUTHORITIES = "SELECT code, name, region FROM geo.authority"
_PEERS = """SELECT p.peer_code AS code, p.rank, p.distance
            FROM geo.authority_peer p WHERE p.code = %s ORDER BY p.rank"""


def _authority_payload(conn: psycopg.Connection, flt: Filter, code: str, y0: int, y1: int) -> dict:
    authorities = {r["code"]: r for r in conn.execute(_AUTHORITIES)}
    if code not in authorities:
        raise NotFound(f"no highway authority {code}")
    counts = authority_counts(conn, flt)
    denoms, every, gaps = _denominators(conn, y0, y1)
    group = {c: (counts.get(c, {}), denoms.get(c, {})) for c in authorities}
    raw = (counts.get(code, {}), every.get(code, {}))  # its own trend shows gap years too
    me = authorities[code]
    peers = conn.execute(_PEERS, (code,)).fetchall()
    peer_codes = [p["code"] for p in peers]
    region = [c for c, a in authorities.items() if a["region"] and a["region"] == me["region"]]
    years = list(range(y0, y1 + 1))

    own = rc.pooled_rates([group[code]])
    peer_rates = {c: rc.pooled_rates([group[c]]) for c in peer_codes}
    peer_stats, ranks = {}, {}
    for name in rc.RATE_NAMES:
        values = [peer_rates[c][name].value for c in peer_codes]
        summary = rc.peer_summary(values)
        peer_stats[name] = _spread(summary)
        rank = rc.rank_of(own[name].value, values)
        ranks[name] = None if rank is None else {"rank": rank[0], "of": rank[1]}

    by_year = []
    for y in years:
        peers_in_year = [rc.pooled_rates([group[c]], {y}) for c in peer_codes]
        year_peer = {
            name: _spread(rc.peer_summary([r[name].value for r in peers_in_year]))
            for name in rc.RATE_NAMES
        }
        by_year.append(
            {
                "year": y,
                "self": _values(rc.pooled_rates([raw], {y})),
                "gap": gaps.get(code, {}).get(y),
                "peers": year_peer,
                "gb": _values(rc.pooled_rates(list(group.values()), {y})),
            }
        )
    return {
        "scope": "authority",
        "authority": dict(me),
        "rates": {
            "self": _rate_json(own),
            "peers": peer_stats,
            "rank": ranks,
            "region": _rate_json(rc.pooled_rates([group[c] for c in region])) if region else None,
            "gb": _rate_json(rc.pooled_rates(list(group.values()))),
        },
        "by_year": by_year,
        "gaps": [{"year": y, "ratio": r} for y, r in sorted(gaps.get(code, {}).items())],
        "peers": [
            {
                "code": p["code"],
                "name": authorities[p["code"]]["name"],
                "region": authorities[p["code"]]["region"],
                "distance": round(p["distance"], 3),
                "rates": _values(peer_rates[p["code"]]),
                "casualties": peer_rates[p["code"]]["per_100k_pop"].count,
            }
            for p in peers
        ],
        "traffic": [
            {
                "year": y,
                "vehicle_km": d.vehicle_km,
                "major_vehicle_km": d.major_vehicle_km,
                "minor_vehicle_km": d.minor_vehicle_km,
            }
            for y, d in sorted(every.get(code, {}).items())
        ],
    }


def _area_payload(conn: psycopg.Connection, flt: Filter, y0: int, y1: int) -> dict:
    """A radius, polygon, district or police force: major roads only, against GB."""
    counts = count_casualties(conn, flt, by_authority=False).get("", {})
    # major roads inside the area, each link clipped to it (FU-047 #6)
    vkm = {r["year"]: r["vehicle_km"] for r in major_vehicle_km(conn, flt.area, (y0, y1))}
    own = rc.rates(counts, {y: rc.Denominators(None, None, v, None, None) for y, v in vkm.items()})
    gb_counts = authority_counts(conn, flt)
    denoms, _, _ = _denominators(conn, y0, y1)
    gb = rc.pooled_rates([(gb_counts.get(c, {}), d) for c, d in denoms.items()])
    return {
        "scope": "area",
        "authority": None,
        "rates": {
            "self": {"major_per_100m_vkm": _rate_json(own)["major_per_100m_vkm"]},
            "peers": None,
            "rank": None,
            "region": None,
            "gb": _rate_json(gb),
        },
        "by_year": [],
        "gaps": [],
        "peers": [],
        "traffic": [{"year": y, "major_vehicle_km": v} for y, v in sorted(vkm.items())],
    }


def _gb_payload(conn: psycopg.Connection, flt: Filter, y0: int, y1: int) -> dict:
    counts = authority_counts(conn, flt)
    denoms, _, _ = _denominators(conn, y0, y1)
    groups = [(counts.get(c, {}), d) for c, d in denoms.items()]
    gb = rc.pooled_rates(groups)
    return {
        "scope": "gb",
        "authority": None,
        "rates": {"self": _rate_json(gb), "peers": None, "rank": None, "region": None, "gb": None},
        "by_year": [
            {"year": y, "self": _values(rc.pooled_rates(groups, {y})), "peers": None, "gb": None}
            for y in range(y0, y1 + 1)
        ],
        "gaps": [],
        "peers": [],
        "traffic": [],
    }


@router.get("/rates")
def area_rates(conn: Conn, flt: Flt) -> dict:
    if not rates_available(conn):
        raise NotFound("authority rates are not built: refresh population and traffic")
    y0, y1 = period(conn, flt)
    scoped = flt.model_copy(update={"year_from": y0, "year_to": y1})
    area = flt.area
    if isinstance(area, AuthorityArea) and area.boundary_type == "highway_authority":
        payload = _authority_payload(conn, scoped, area.code, y0, y1)
    elif area is not None:
        payload = _area_payload(conn, scoped, y0, y1)
    else:
        payload = _gb_payload(conn, scoped, y0, y1)
    return ok(payload | {"year_from": y0, "year_to": y1})
