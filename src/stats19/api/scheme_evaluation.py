"""/api/schemes/{id}/evaluation: did the scheme work? (PLAN-011 §3, V5 S3)

Counts the scheme's collisions in its stored footprint over the before and after periods,
then:

- **Empirical Bayes** for a junction or link that has a safety model today: the model and
  its yearly calibration factors give what was expected without the scheme, allowing for
  regression to the mean and the trend (stats19.evaluation.eb_before_after).
- **Comparison group** otherwise: the change at the scheme against the change in the rest
  of its highway authority, on the same road classes (D5). If the footprint is most of the
  authority, the rest of Great Britain stands in.

A junction scheme counts only junction collisions (STATS19's junction fields, as the junction
page and its model do: FU-057); a link scheme only the rest (stats19.api.schemes.counted).
Results are cached per data load and scheme version, since nothing else changes them.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from datetime import date
from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends

from stats19 import evaluation as ev
from stats19.api import cache
from stats19.api.deps import get_conn
from stats19.api.envelope import NotFound, ok
from stats19.api.org import current_org
from stats19.api.scheme_periods import Period, scheme_periods
from stats19.api.schemes import _LIVE, LINE_MATCH_M, counted, period_json, year_span
from stats19.reference.safety import empirical_bayes
from stats19.reference.safety_build import SAFETY_YEARS
from stats19.reference.swap import tables_exist

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Org = Annotated[UUID, Depends(current_org)]

#: A footprint covering more than this share of its authority is compared with the rest of GB
WHOLE_AUTHORITY = 0.5
_CACHE: OrderedDict[str, dict] = OrderedDict()
_CACHE_MAX = 256
_LOCK = threading.Lock()

_IN_PERIODS = """(c.collision_date BETWEEN %(b0)s AND %(b1)s
                  OR c.collision_date BETWEEN %(a0)s AND %(a1)s)"""
_COUNTS = """count(*) FILTER (WHERE c.collision_date <= %(b1)s) AS before,
             count(*) FILTER (WHERE c.collision_date >= %(a0)s) AS after"""


@router.get("/schemes/{scheme_id}/evaluation")
def scheme_evaluation(scheme_id: UUID, conn: Conn, org: Org) -> dict:
    scheme = conn.execute(
        f"""SELECT s.id, s.version, s.site_type, s.site_ref, s.works_start, s.works_end,
                   s.before_years, s.after_years, s.cost::float AS cost, s.fyrr,
                   ST_Dimension(s.geom_bng) AS dim
            FROM app.scheme s WHERE s.id = %(id)s AND {_LIVE}""",
        {"id": scheme_id, "org": org},
    ).fetchone()
    if scheme is None:
        raise NotFound("No such scheme.")
    load = cache.data_load(conn)
    key = f"{load}|{org}|{scheme_id}|{scheme['version']}"
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return ok(_CACHE[key])
    result = evaluate(conn, scheme) | {"data_load": load}
    with _LOCK:
        _CACHE[key] = result
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    return ok(result)


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()


def evaluate(conn: psycopg.Connection, scheme: dict) -> dict:
    first_year, last_year = year_span(conn)
    p = scheme_periods(
        scheme["works_start"],
        scheme["works_end"],
        scheme["before_years"],
        scheme["after_years"],
        last_year,
    )
    base: dict[str, Any] = {
        "stage": p.stage,
        "after_months": p.after_months,
        "after_months_wanted": p.after_months_wanted,
        "before": None,
        "after": None,
        "method": None,
        "method_note": None,
        "counts": None,
        "result": None,
        "verdict": None,
        "headline": None,
        "eb": None,
        "comparison": None,
        "value": None,
    }
    if p.before is None:
        return base | {"message": "Add the works dates to evaluate the scheme."}
    if p.after is None:
        return base | {"message": "The evaluation starts once the works have an end date."}
    if first_year is None or p.data_end is None:
        return base | {"message": "No collision data is loaded yet."}
    before = ev.clip(p.before, p.data_end)
    data_start = date(first_year, 1, 1)
    if before is None or before.end < data_start:
        return base | {"message": "The before period is earlier than the loaded data."}
    before = Period(max(before.start, data_start), before.end)
    after = ev.clip(p.after, p.data_end)
    base |= {"before": period_json(before), "after": period_json(after)}
    if after is None:
        year = p.after.start.year
        return base | {
            "message": f"No after-data yet: DfT publishes {year}'s collisions in September "
            f"{year + 1}."
        }
    return base | _evaluate_periods(conn, scheme, before, after, p.after_months)


def _evaluate_periods(
    conn: psycopg.Connection, scheme: dict, before: Period, after: Period, after_months: int
) -> dict:
    kind, _ = counted(conn, scheme["site_type"])
    params = {
        "id": scheme["id"],
        "within": 0.0 if scheme["dim"] == 2 else LINE_MATCH_M,
        "b0": before.start,
        "b1": before.end,
        "a0": after.start,
        "a1": after.end,
    }
    counts = conn.execute(
        f"""SELECT {_COUNTS},
                   count(*) FILTER (WHERE c.collision_date <= %(b1)s
                                      AND c.collision_severity < 3) AS ksi_before,
                   count(*) FILTER (WHERE c.collision_date >= %(a0)s
                                      AND c.collision_severity < 3) AS ksi_after,
                   coalesce(array_agg(DISTINCT c.first_road_class)
                            FILTER (WHERE c.first_road_class IS NOT NULL), '{{}}') AS classes
            FROM core.collision c, app.scheme s
            WHERE s.id = %(id)s AND ST_DWithin(c.geom_bng, s.geom_bng, %(within)s)
              AND {_IN_PERIODS} AND {kind}""",
        params,
    ).fetchone()
    out: dict[str, Any] = {
        "message": None,
        "counts": {k: counts[k] for k in ("before", "after", "ksi_before", "ksi_after")},
    }
    model = _site_model(conn, scheme)
    result = None
    if model is not None:
        try:
            result, out["eb"] = _eb(conn, model, counts, before, after)
            out |= {
                "method": "eb",
                "method_note": f"Empirical Bayes, using the safety model for similar "
                f"{_units(scheme['site_type'])} ({model['peer_group']}) and its yearly trend.",
            }
        except ValueError:
            result = None
    if result is None:
        out |= {"method": "comparison", "method_note": _why_comparison(scheme, model)}
        try:
            result, out["comparison"] = _comparison(conn, params, kind, counts)
        except ValueError as exc:
            return out | {"message": _comparison_problem(str(exc))}
    return out | _outcome(result, after, after_months, scheme)


def _units(site_type: str) -> str:
    return "junctions" if site_type == "junction" else "roads"


def _site_model(conn: psycopg.Connection, scheme: dict) -> dict | None:
    """The site's safety model today, if it has one."""
    if scheme["site_type"] not in ("junction", "link") or not scheme["site_ref"]:
        return None
    if not tables_exist(conn, "geo.safety_unit", "geo.safety_model", "geo.safety_calibration"):
        return None
    row = conn.execute(
        """SELECT u.peer_group, u.predicted, m.alpha
           FROM geo.safety_unit u
           JOIN geo.safety_model m ON m.unit_type = u.unit_type AND m.peer_group = u.peer_group
           WHERE u.unit_type = %s AND u.unit_id = %s AND u.predicted > 0""",
        (scheme["site_type"], scheme["site_ref"]),
    ).fetchone()
    return None if row is None else row | {"unit_type": scheme["site_type"]}


def _eb(
    conn: psycopg.Connection, model: dict, counts: dict, before: Period, after: Period
) -> tuple[ev.Result, dict]:
    calibration = {
        r["year"]: r["factor"]
        for r in conn.execute(
            """SELECT year, factor FROM geo.safety_calibration
               WHERE unit_type = %s AND peer_group = %s ORDER BY year""",
            (model["unit_type"], model["peer_group"]),
        )
    }
    per_year = model["predicted"] / SAFETY_YEARS
    years = range(before.start.year, after.end.year + 1)
    spf = dict.fromkeys(years, per_year)
    mu_b = ev.period_prediction(spf, calibration, before)
    mu_a = ev.period_prediction(spf, calibration, after)
    result = ev.eb_before_after(counts["before"], counts["after"], mu_b, mu_a, model["alpha"])
    eb_before, _, _ = empirical_bayes(counts["before"], mu_b, model["alpha"])
    return result, {
        "peer_group": model["peer_group"],
        "alpha": round(model["alpha"], 4),
        "mu_before": round(mu_b, 3),
        "mu_after": round(mu_a, 3),
        "eb_before": round(eb_before, 3),
        "calibration": {str(y): round(f, 3) for y, f in calibration.items()},
    }


def _why_comparison(scheme: dict, model: dict | None) -> str:
    if scheme["site_type"] in ("junction", "link") and model is None:
        return (
            "Comparison group: this site has no safety model today (not every major arm's "
            "traffic is counted, or the site has changed), so regression to the mean can't "
            "be allowed for."
        )
    if scheme["site_type"] in ("junction", "link"):
        return "Comparison group: the safety model couldn't predict for these periods."
    return "Comparison group: areas, routes and clusters have no safety model."


def _comparison(
    conn: psycopg.Connection, params: dict, kind: str, counts: dict
) -> tuple[ev.Result, dict]:
    area = _comparison_area(conn, params["id"])
    classes = list(counts["classes"])
    where = ["c.geom_bng IS NOT NULL", _IN_PERIODS, kind]
    where.append("NOT ST_DWithin(c.geom_bng, s.geom_bng, %(within)s)")
    if classes:
        where.append("c.first_road_class = ANY(%(classes)s)")
    join = ""
    if area["code"] is not None:
        join = """JOIN geo.boundary b ON b.boundary_type = 'highway_authority'
                  AND b.code = %(code)s AND ST_Intersects(b.geom_bng, c.geom_bng)"""
    row = conn.execute(
        f"""SELECT {_COUNTS} FROM core.collision c {join}, app.scheme s
            WHERE s.id = %(id)s AND {" AND ".join(where)}""",
        params | {"classes": classes, "code": area["code"]},
    ).fetchone()
    result = ev.comparison_group(counts["before"], counts["after"], row["before"], row["after"])
    return result, area | {
        "before": row["before"],
        "after": row["after"],
        "road_classes": sorted(classes),
    }


def _comparison_area(conn: psycopg.Connection, scheme_id: UUID) -> dict:
    """The highway authority the footprint is in, or Great Britain when the footprint is
    most of its authority (or no boundaries are loaded)."""
    gb = {"code": None, "name": "the rest of Great Britain"}
    if not tables_exist(conn, "geo.boundary"):
        return gb
    row = conn.execute(
        """SELECT b.code, b.name,
                  ST_Area(ST_Intersection(b.geom_bng, s.geom_bng))
                      / nullif(ST_Area(b.geom_bng), 0) AS share
           FROM app.scheme s
           JOIN geo.boundary b ON b.boundary_type = 'highway_authority'
                AND ST_Intersects(b.geom_bng, ST_PointOnSurface(s.geom_bng))
           WHERE s.id = %s LIMIT 1""",
        (scheme_id,),
    ).fetchone()
    if row is None or (row["share"] or 0) > WHOLE_AUTHORITY:
        return gb
    return {"code": row["code"], "name": f"the rest of {row['name']}"}


def _comparison_problem(reason: str) -> str:
    if "scheme" in reason:
        return "No collisions at the scheme in either period, so there's no change to measure."
    return "The comparison area has no collisions in these periods, so there's nothing to compare."


def _outcome(result: ev.Result, after: Period, after_months: int, scheme: dict) -> dict:
    years = ev.years_of(after)
    saved_a_year = result.saved / years
    return {
        "result": {
            "theta": round(result.theta, 4),
            "lower": round(result.lower, 4),
            "upper": round(result.upper, 4),
            "change_pct": round(result.change_pct, 1),
            "observed_after": result.observed_after,
            "expected_after": round(result.expected_after, 2),
            "saved_a_year": round(saved_a_year, 2),
        },
        "verdict": ev.verdict(result, after_months),
        "headline": ev.describe(result, after_months),
        "value": _value(saved_a_year, scheme),
    }


def _value(saved_a_year: float, scheme: dict) -> dict | None:
    """The saving valued at the scheme's own FYRR price, and achieved against expected FYRR."""
    fyrr = scheme["fyrr"]
    if not fyrr:
        return None
    vpc = fyrr["value_per_collision"]
    cost = scheme["cost"]
    expected = fyrr["collisions_per_year"] * fyrr["reduction_pct"] / 100
    return {
        "value_per_collision": vpc,
        "prices_year": fyrr.get("prices_year"),
        "saved_a_year_value": round(saved_a_year * vpc),
        "expected_saved_a_year": round(expected, 2),
        "achieved_fyrr_pct": round(ev.fyrr_pct(saved_a_year, vpc, cost), 1) if cost else None,
        "expected_fyrr_pct": round(ev.fyrr_pct(expected, vpc, cost), 1) if cost else None,
    }
