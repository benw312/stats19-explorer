"""/api/routes: roads in an area ranked, and one road as a corridor (PLAN-009 V2, B2).

A route is a road number within the filter's area. Its pieces are the count point links
the safety model scored (PLAN-008 T4) and the scored junctions with an arm on the road,
so every figure matches the site cards. A link's collisions include those at junctions
along it (EuroRAP style), so route totals add links only.
"""

from __future__ import annotations

import json
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, Path, Query
from psycopg import sql

from stats19.api.corridor_order import Link, chain, fraction_along, link_ends
from stats19.api.deps import get_conn
from stats19.api.envelope import ok
from stats19.api.filters import Filter, area_condition, filter_param
from stats19.api.prevention import prevention_values, value_per_collision
from stats19.reference.safety_build import SAFETY_YEARS
from stats19.reference.swap import tables_exist

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Flt = Annotated[Filter, Depends(filter_param)]

ROAD_PATTERN = r"^[AM][0-9]{1,4}(\(M\))?$"
MAX_ROUTES = 50
MIN_RATE_KM = 2.0  # shorter routes' rates are too noisy to rank by
JUNCTION_SNAP_M = 150
SIMPLIFY_M = 10
VKM_UNIT = 1e8  # rates per 100 million vehicle-km, as the site cards
NEEDED = ("geo.safety_unit", "geo.safety_model", "geo.traffic_stretch", "core.collision")


def band_of(excess: float | None, rank: int | None, size: int | None) -> int | None:
    """The risk layer's band: 3 worst 1%, 2 worst 5%, 1 worst 20%, 0 middle, -1 best 20%."""
    if excess is None or rank is None or not size:
        return None
    if excess > 0 and rank <= 0.01 * size:
        return 3
    if excess > 0 and rank <= 0.05 * size:
        return 2
    if excess > 0 and rank <= 0.20 * size:
        return 1
    if rank > 0.80 * size:
        return -1
    return 0


def _area(flt: Filter, geom: str) -> tuple[sql.Composable, dict]:
    if flt.area is None:
        return sql.SQL("TRUE"), {}
    cond, params = area_condition(flt.area)
    # area_condition expects the alias c with geom_bng
    return sql.SQL("EXISTS (SELECT 1 FROM (SELECT {g} AS geom_bng) c WHERE {cond})").format(
        g=sql.SQL(geom), cond=cond
    ), params


def _period(conn: psycopg.Connection) -> tuple[int, int] | None:
    latest = conn.execute("SELECT max(collision_year) AS y FROM core.collision").fetchone()["y"]
    return None if latest is None else (latest - SAFETY_YEARS + 1, latest)


def _figures(row: dict, values: dict[int, float]) -> dict:
    """A scored site's figures, with its excess valued a year at its group's severity mix."""
    totals = (row.pop("observed_total"), row.pop("ksi_total"), row.pop("fatal_total"))
    vpc = None if totals[0] is None else value_per_collision(*totals, values)
    excess = row.get("excess")
    row["band"] = band_of(excess, row.pop("excess_rank"), row.pop("group_size"))
    row["value_per_year"] = (
        None if vpc is None or excess is None else round(excess / SAFETY_YEARS * vpc)
    )
    return row


def _vkm(flow: float | None, length_km: float | None) -> float:
    """Vehicle-km over the period, in units of 100 million."""
    if not flow or not length_km:
        return 0.0
    return flow * length_km * 365 * SAFETY_YEARS / VKM_UNIT


def _rate(observed: int, vkm: float) -> float | None:
    return round(observed / vkm, 1) if vkm > 0 else None


def summarise(links: list[dict]) -> dict:
    """Route totals from its scored links' figures (unscored links add length only)."""
    scored = [x for x in links if x.get("observed") is not None]
    vkm = sum(_vkm(x.get("flow"), x.get("length_km")) for x in scored)
    observed = sum(x["observed"] for x in scored)
    excess = [x["excess"] for x in scored if x.get("excess") is not None]
    values = [x["value_per_year"] for x in scored if x.get("value_per_year") is not None]
    return {
        "links": len(links),
        "scored": len(scored),
        "length_km": round(sum(x.get("length_km") or 0 for x in links), 2),
        "observed": observed,
        "ksi": sum(x.get("ksi") or 0 for x in scored),
        "vkm_100m": round(vkm, 3),
        "per_100m_vkm": _rate(observed, vkm),
        "excess": round(sum(excess), 2) if excess else None,
        # the worse links only: a long road that's mostly fine can't hide a bad stretch
        "excess_worse": round(sum(e for e in excess if e > 0), 2) if excess else None,
        "value_per_year": sum(values) if values else None,
        "worst_5pct": sum(1 for x in scored if (x.get("band") or 0) >= 2),
    }


_GROUP = "m.observed_total, m.ksi_total, m.fatal_total"

_RANK_LINKS = f"""
SELECT p.road_name AS road, p.road_category, u.observed, u.ksi, u.predicted, u.excess,
       u.excess_rank, u.group_size, u.length_km, u.flow, {_GROUP}
FROM geo.safety_unit u
JOIN geo.traffic_count_point p ON p.count_point_id::text = u.unit_id
LEFT JOIN geo.safety_model m ON m.unit_type = u.unit_type AND m.peer_group = u.peer_group
WHERE u.unit_type = 'link' AND p.road_name ~ %(pattern)s AND {{area}}
"""


@router.get("/routes")
def routes(
    conn: Conn,
    flt: Flt,
    sort: Literal["excess", "worse", "rate"] = "excess",
    limit: Annotated[int, Query(ge=1, le=MAX_ROUTES)] = 25,
) -> dict:
    """Roads in the area ranked by net excess, by the excess on their worse links, or by rate."""
    if not tables_exist(conn, *NEEDED):
        return ok({"available": False, "routes": []})
    area, params = _area(flt, "u.geom_bng")
    rows = conn.execute(
        sql.SQL(_RANK_LINKS).format(area=area), params | {"pattern": ROAD_PATTERN}
    ).fetchall()
    price_year, values = prevention_values(conn)
    by_road: dict[str, list[dict]] = {}
    category: dict[str, str] = {}
    for r in rows:
        category.setdefault(r["road"], r["road_category"])
        by_road.setdefault(r["road"], []).append(_figures(dict(r), values))
    ranked = [
        {"road": road, "road_category": category[road]} | summarise(links)
        for road, links in by_road.items()
    ]
    if sort == "rate":
        ranked = [
            r for r in ranked if r["length_km"] >= MIN_RATE_KM and r["per_100m_vkm"] is not None
        ]
        ranked.sort(key=lambda r: (-r["per_100m_vkm"], r["road"]))
    elif sort == "worse":
        ranked.sort(key=lambda r: (-(r["excess_worse"] or 0), r["road"]))
    else:
        ranked.sort(key=lambda r: (-(r["excess"] or 0), r["road"]))
    period = _period(conn)
    return ok(
        {
            "available": True,
            "sort": sort,
            "min_rate_km": MIN_RATE_KM,
            "year_from": period[0] if period else None,
            "year_to": period[1] if period else None,
            "years": SAFETY_YEARS,
            "price_year": price_year,
            "total": len(ranked),
            "routes": ranked[:limit],
        }
    )


# the part ends of each link's traced stretch, for chaining
_ENDS = """
ARRAY(SELECT ARRAY[ST_X(e.p), ST_Y(e.p)] FROM (
    SELECT ST_StartPoint(d.geom) AS p FROM ST_Dump(s.geom_bng) d
    UNION ALL SELECT ST_EndPoint(d.geom) FROM ST_Dump(s.geom_bng) d) e)"""

_CORRIDOR_LINKS = f"""
SELECT p.count_point_id, p.road_category, p.start_junction, p.end_junction, p.latest_aadf,
       u.peer_group, u.observed, u.ksi, u.predicted, u.excess, u.excess_rank, u.group_size,
       coalesce(u.length_km, s.length_m / 1000) AS length_km, u.flow, {_GROUP},
       {_ENDS} AS ends,
       ST_AsGeoJSON(ST_Transform(ST_Simplify(s.geom_bng, {SIMPLIFY_M}), 4326), 5) AS geometry
FROM geo.traffic_count_point p
JOIN geo.traffic_stretch s USING (count_point_id)
LEFT JOIN geo.safety_unit u ON u.unit_type = 'link' AND u.unit_id = p.count_point_id::text
LEFT JOIN geo.safety_model m ON m.unit_type = u.unit_type AND m.peer_group = u.peer_group
WHERE p.road_name = %(road)s AND s.method = 'major' AND {{area}}
"""

_CORRIDOR_JUNCTIONS = f"""
SELECT j.id, j.name, j.kind, j.motorway_junction, u.peer_group, u.observed, u.ksi,
       u.predicted, u.excess, u.excess_rank, u.group_size, {_GROUP},
       ST_X(j.geom_bng) AS x, ST_Y(j.geom_bng) AS y, near.count_point_id
FROM geo.junction j
JOIN geo.safety_unit u ON u.unit_type = 'junction' AND u.unit_id = j.id
LEFT JOIN geo.safety_model m ON m.unit_type = u.unit_type AND m.peer_group = u.peer_group
CROSS JOIN LATERAL (
    SELECT s.count_point_id FROM geo.traffic_stretch s
    WHERE s.count_point_id = ANY(%(links)s) AND ST_DWithin(s.geom_bng, j.geom_bng, %(snap)s)
    ORDER BY s.geom_bng <-> j.geom_bng LIMIT 1
) near
WHERE EXISTS (SELECT 1 FROM geo.junction_arm a
              WHERE a.junction_id = j.id AND a.road_number = %(road)s)
  AND {{area}}
"""


def _ordered_links(rows: list[dict], values: dict[int, float]) -> list[dict]:
    by_key = {str(r["count_point_id"]): r for r in rows}
    placed = chain(
        [
            Link(key, *link_ends([tuple(p) for p in r["ends"]]), r["length_km"] or 0.0)
            for key, r in by_key.items()
        ]
    )
    out = []
    for p in placed:
        r = dict(by_key[p.key])
        r.pop("ends")
        scored = r["observed"] is not None
        r = _figures(r, values) if scored else _unscored(r)
        out.append(
            r
            | {
                "geometry": json.loads(r["geometry"]),
                "gap_before_km": round(p.gap_before_km, 2),
                "per_100m_vkm": _rate(r["observed"], _vkm(r["flow"], r["length_km"]))
                if scored
                else None,
                "_ends": (p.start, p.end),
            }
        )
    return out


def _unscored(r: dict) -> dict:
    for k in ("observed_total", "ksi_total", "fatal_total", "excess_rank", "group_size"):
        r.pop(k, None)
    return r | {"band": None, "value_per_year": None}


def _placed_junctions(rows: list[dict], links: list[dict], values: dict[int, float]) -> list[dict]:
    index = {str(x["count_point_id"]): i for i, x in enumerate(links)}
    out = []
    for r in rows:
        i = index[str(r.pop("count_point_id"))]
        start, end = links[i]["_ends"]
        frac = fraction_along(start, end, (r.pop("x"), r.pop("y")))
        out.append(_figures(dict(r), values) | {"link": i, "frac": round(frac, 3)})
    out.sort(key=lambda j: (j["link"], j["frac"]))
    return out


@router.get("/routes/{road}")
def corridor(
    conn: Conn,
    flt: Flt,
    road: Annotated[str, Path(pattern=ROAD_PATTERN, max_length=10)],
) -> dict:
    """One road in the area as a corridor: its links in order, its junctions placed on them."""
    if not tables_exist(conn, *NEEDED, "geo.junction", "geo.junction_arm"):
        return ok({"available": False, "road": road, "links": [], "junctions": []})
    price_year, values = prevention_values(conn)
    area, params = _area(flt, "p.geom_bng")
    link_rows = conn.execute(
        sql.SQL(_CORRIDOR_LINKS).format(area=area), params | {"road": road}
    ).fetchall()
    links = _ordered_links(link_rows, values)
    junctions: list[dict] = []
    if links:
        area, params = _area(flt, "j.geom_bng")
        rows = conn.execute(
            sql.SQL(_CORRIDOR_JUNCTIONS).format(area=area),
            params
            | {
                "road": road,
                "links": [x["count_point_id"] for x in links],
                "snap": JUNCTION_SNAP_M,
            },
        ).fetchall()
        junctions = _placed_junctions(rows, links, values)
    for x in links:
        x.pop("_ends")
    period = _period(conn)
    return ok(
        {
            "available": True,
            "road": road,
            "road_category": links[0]["road_category"] if links else None,
            "year_from": period[0] if period else None,
            "year_to": period[1] if period else None,
            "years": SAFETY_YEARS,
            "price_year": price_year,
            "totals": summarise(links),
            "links": links,
            "junctions": junctions,
        }
    )
