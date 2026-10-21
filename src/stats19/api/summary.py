"""/api/summary: everything the summary panel and area report need, in one query.

The filtered collisions are materialised once (CTE ``sel``) and every breakdown is
computed from it, so the filter runs a single time per request.
"""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends
from psycopg import sql

from stats19.api.deps import get_conn
from stats19.api.envelope import ApiError, ok
from stats19.api.filters import (
    Filter,
    collision_relation,
    compile_filter,
    count_capped,
    filter_param,
)

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Flt = Annotated[Filter, Depends(filter_param)]

# County-scale summaries take ~0.15 s; all of GB for five years ~8 s. Cap it so the
# UI asks for an area instead of tying up a connection.
MAX_SUMMARY_COLLISIONS = 200_000

# Collision-level coded fields broken down in the summary (order = display order).
BREAKDOWN_FIELDS = (
    "light_conditions",
    "weather_conditions",
    "road_surface_conditions",
    "speed_limit",
    "first_road_class",
    "road_type",
    "junction_detail",
    "urban_or_rural_area",
)

_SEV = """count(*) FILTER (WHERE {col} = 1) AS fatal,
          count(*) FILTER (WHERE {col} = 2) AS serious,
          count(*) FILTER (WHERE {col} = 3) AS slight"""


def _breakdown(field: str) -> str:
    return f"""'{field}', (
        SELECT coalesce(jsonb_agg(jsonb_build_object('code', code, 'label', label, 'n', n)
                                  ORDER BY n DESC, code), '[]'::jsonb)
        FROM (SELECT s.{field} AS code, l.label, count(*) AS n
              FROM sel s
              LEFT JOIN core.lookup_code l ON l.table_name = 'collision'
                   AND l.field_name = '{field}' AND l.code = s.{field}::text
              WHERE s.{field} IS NOT NULL
              GROUP BY 1, 2) b)"""


def summary_sql(rel: sql.Composable, where: sql.Composable) -> sql.Composable:
    fields = ", ".join(f"c.{f}" for f in BREAKDOWN_FIELDS)
    breakdowns = ",\n".join(_breakdown(f) for f in BREAKDOWN_FIELDS)
    template = f"""
WITH sel AS MATERIALIZED (
    SELECT c.collision_index, c.collision_year, c.collision_severity, c.day_of_week,
           c.collision_adjusted_severity_serious AS adj_serious,
           extract(hour FROM c.collision_time)::int AS hour, {fields}
    FROM {{rel}} c WHERE {{where}}
), cas AS MATERIALIZED (
    SELECT k.casualty_severity, k.age_band_of_casualty, g.road_user_group
    FROM sel JOIN core.casualty k USING (collision_index)
    LEFT JOIN mart.road_user_group g ON g.code = k.casualty_type
)
SELECT jsonb_build_object(
  'totals', (SELECT jsonb_build_object(
                 'collisions', count(*),
                 'fatal', count(*) FILTER (WHERE collision_severity = 1),
                 'serious', count(*) FILTER (WHERE collision_severity = 2),
                 'slight', count(*) FILTER (WHERE collision_severity = 3),
                 'ksi', count(*) FILTER (WHERE collision_severity IN (1, 2)),
                 -- DfT's adjusted severity: comparable between forces (FU-047 #10)
                 'ksi_adjusted', round(coalesce(sum(CASE WHEN collision_severity = 1 THEN 1
                     ELSE coalesce(adj_serious, (collision_severity = 2)::int) END), 0)))
             FROM sel)
            || (SELECT jsonb_build_object(
                 'casualties', count(*),
                 'casualties_fatal', count(*) FILTER (WHERE casualty_severity = 1),
                 'casualties_serious', count(*) FILTER (WHERE casualty_severity = 2),
                 'casualties_slight', count(*) FILTER (WHERE casualty_severity = 3))
                FROM cas),
  'by_year', (SELECT coalesce(jsonb_agg(to_jsonb(y) ORDER BY y.year), '[]'::jsonb)
              FROM (SELECT collision_year AS year, {_SEV.format(col="collision_severity")}
                    FROM sel GROUP BY 1) y),
  'by_dow_hour', (SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb)
                  FROM (SELECT day_of_week AS dow, hour, count(*) AS n FROM sel
                        WHERE hour IS NOT NULL AND day_of_week BETWEEN 1 AND 7
                        GROUP BY 1, 2) t),
  'breakdowns', jsonb_build_object({breakdowns}),
  'casualties_by_group', (SELECT coalesce(jsonb_agg(to_jsonb(g) ORDER BY g.total DESC), '[]'::jsonb)
                          FROM (SELECT coalesce(road_user_group, 'unknown') AS "group",
                                       {_SEV.format(col="casualty_severity")},
                                       count(*) AS total
                                FROM cas GROUP BY 1) g),
  'casualties_by_age_band', (
      SELECT coalesce(jsonb_agg(jsonb_build_object('code', code, 'label', label, 'n', n)
                                ORDER BY code), '[]'::jsonb)
      FROM (SELECT c.age_band_of_casualty AS code, l.label, count(*) AS n FROM cas c
            LEFT JOIN core.lookup_code l ON l.table_name = 'casualty'
                 AND l.field_name = 'age_band_of_casualty'
                 AND l.code = c.age_band_of_casualty::text
            WHERE c.age_band_of_casualty IS NOT NULL GROUP BY 1, 2) a),
  'vehicles_by_group', (
      SELECT coalesce(jsonb_agg(jsonb_build_object('group', grp, 'n', n) ORDER BY n DESC),
                      '[]'::jsonb)
      FROM (SELECT coalesce(g.road_user_group, 'unknown') AS grp, count(*) AS n
            FROM sel JOIN core.vehicle v USING (collision_index)
            LEFT JOIN mart.road_user_group g ON g.code = v.vehicle_type
            GROUP BY 1) v)
) AS summary
"""
    return sql.SQL(template).format(rel=rel, where=where)


def run_summary(conn: psycopg.Connection, flt: Filter) -> dict:
    where, params = compile_filter(flt)
    row = conn.execute(summary_sql(collision_relation(flt), where), params).fetchone()
    return row["summary"]


@router.get("/summary")
def summary(conn: Conn, flt: Flt) -> dict:
    if count_capped(conn, flt, MAX_SUMMARY_COLLISIONS) > MAX_SUMMARY_COLLISIONS:
        raise ApiError(
            413,
            "too_large",
            f"Summaries cover up to {MAX_SUMMARY_COLLISIONS:,} collisions. "
            "Choose an area or a shorter period.",
        )
    return ok(run_summary(conn, flt))
