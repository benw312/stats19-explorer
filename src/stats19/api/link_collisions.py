"""Collisions on the roads a DfT count covers, and the rate per vehicle-km (PLAN-008 T3b).

A collision belongs to a count point when its matched OS link position (geo.collision_link)
falls in one of that count point's link pieces (geo.traffic_link). The rate follows the
EuroRAP risk-map measure: all collisions along the road per 100 million vehicle-km, with
those also assigned to a junction counted separately so a between-junctions rate is
available too. Collisions on roundabout rings and slip roads belong to junctions, never links.
"""

from __future__ import annotations

import psycopg
from psycopg import sql

from stats19.api.filters import Filter, collision_relation, compile_filter
from stats19.api.junctions import DAYS_PER_YEAR, collision_period, summarise_collisions
from stats19.reference.collision_links import REVIEW_BELOW
from stats19.reference.swap import tables_exist

VEHICLE_KM_UNIT = 1e8  # rates per 100 million vehicle-km

_ROWS = """
SELECT c.collision_index, c.collision_year AS year, c.collision_severity AS severity,
       c.junction_control AS control, jc.junction_id IS NOT NULL AS at_junction,
       m.score
FROM geo.traffic_link t
JOIN geo.collision_link m
  ON m.link_id = t.link_id AND m.frac >= t.frac_from AND (m.frac < t.frac_to OR t.frac_to >= 1)
JOIN {rel} c ON c.collision_index = m.collision_index
LEFT JOIN geo.junction_collision jc ON jc.collision_index = m.collision_index
WHERE t.count_point_id = %(cp)s AND {where}
ORDER BY c.collision_year DESC, c.collision_index
"""


def link_rate(collisions: int, length_km: float, aadf: float, years: int) -> float | None:
    """Collisions per 100 million vehicle-km."""
    vkm = length_km * aadf * DAYS_PER_YEAR * years
    return None if vkm <= 0 else round(collisions / (vkm / VEHICLE_KM_UNIT), 2)


def link_collisions(
    conn: psycopg.Connection, flt: Filter, count_point_id: int, length_m: float | None
) -> dict | None:
    if not tables_exist(conn, "geo.collision_link", "geo.traffic_link", "geo.junction_collision"):
        return None
    period = collision_period(conn, flt)
    if period is None:
        return None
    year_from, year_to, _ = period
    scoped = flt.model_copy(update={"year_from": year_from, "year_to": year_to})
    where, params = compile_filter(scoped)
    rows = conn.execute(
        sql.SQL(_ROWS).format(rel=collision_relation(scoped), where=where),
        params | {"cp": count_point_id},
    ).fetchall()
    aadf = conn.execute(
        """SELECT avg(all_motor_vehicles) AS a FROM geo.traffic_aadf
           WHERE count_point_id = %s AND year BETWEEN %s AND %s""",
        (count_point_id, year_from, year_to),
    ).fetchone()["a"]
    years = year_to - year_from + 1
    at_junction = sum(r["at_junction"] for r in rows)
    length_km = (length_m or 0) / 1000
    rate = between = None
    if aadf and length_km:
        rate = link_rate(len(rows), length_km, float(aadf), years)
        between = link_rate(len(rows) - at_junction, length_km, float(aadf), years)
    return summarise_collisions(rows, year_from, year_to) | {
        "at_junctions": at_junction,
        "low_confidence": sum(r["score"] < REVIEW_BELOW for r in rows),
        "length_km": round(length_km, 2),
        "period_aadf": round(aadf) if aadf else None,
        "per_100m_vkm": rate,
        "per_100m_vkm_between_junctions": between,
    }
