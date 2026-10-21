"""Build geo.safety_unit / geo.safety_model: SPFs and EB excess for links and junctions,
and geo.safety_calibration: each model's yearly trend factors (for scheme evaluation).

PLAN-008 §10. Period: the last ``SAFETY_YEARS`` years of collision data. Rebuilt after the
collision matches, a traffic reload, an OSM reload and each STATS19 load.
"""

from __future__ import annotations

import json
import logging
import math
from collections import defaultdict

import numpy as np
import psycopg

from stats19.reference import safety as sf
from stats19.reference import safety_calibration as cal
from stats19.reference.junction_build import COLLISION_YEARS
from stats19.reference.swap import swap_tables, tables_exist

log = logging.getLogger(__name__)

SAFETY_YEARS = 5
MIN_FIT_SIZE = 30  # sites needed to fit a model at all (groups merge up to MIN_GROUP_SIZE)
_DENSITY_RADIUS_M = 500.0
_AUTHORITY = """(SELECT b.code FROM geo.boundary b
     WHERE b.boundary_type = 'highway_authority' AND ST_Intersects(b.geom_bng, {geom}) LIMIT 1)"""

_CP_AADF = """
CREATE TEMP TABLE cp_aadf ON COMMIT DROP AS
SELECT count_point_id, avg(all_motor_vehicles)::double precision AS aadf
FROM geo.traffic_aadf WHERE year BETWEEN %(y0)s AND %(y1)s AND all_motor_vehicles > 0
GROUP BY count_point_id
"""

# Links: current major count points with a traced OS link. Collisions that are junction
# collisions belong to the junction's model, so links count the rest.
_LINKS = f"""
WITH cp AS (
    SELECT p.count_point_id, p.road_category, s.length_m / 1000.0 AS length_km, a.aadf,
           ST_PointOnSurface(s.geom_bng) AS mid
    FROM geo.traffic_count_point p
    JOIN geo.traffic_stretch s USING (count_point_id)
    JOIN cp_aadf a USING (count_point_id)
    WHERE p.road_type = 'Major' AND p.quality < 3 AND s.method = 'major'
      AND p.road_category IN ('TM', 'PM', 'TA', 'PA') AND s.length_m > 0
), dual AS (
    SELECT t.count_point_id,
           sum(l.length_m * (t.frac_to - t.frac_from)) FILTER (
               WHERE l.form_of_way IN ('Dual Carriageway', 'Collapsed Dual Carriageway'))
           / nullif(sum(l.length_m * (t.frac_to - t.frac_from)), 0) AS dual_share
    FROM geo.traffic_link t JOIN geo.road_link l ON l.id = t.link_id
    WHERE t.method = 'major' GROUP BY t.count_point_id
), n AS (
    SELECT t.count_point_id, count(*) AS n, count(*) FILTER (WHERE c.collision_severity < 3) AS ksi,
           count(*) FILTER (WHERE c.collision_severity = 1) AS fatal
    FROM geo.traffic_link t
    JOIN geo.collision_link m
      ON m.link_id = t.link_id AND m.frac >= t.frac_from AND (m.frac < t.frac_to OR t.frac_to >= 1)
    JOIN core.collision c ON c.collision_index = m.collision_index
    WHERE t.method = 'major' AND c.collision_year BETWEEN %(y0)s AND %(y1)s
      AND NOT EXISTS (SELECT 1 FROM geo.junction_collision jc
                      WHERE jc.collision_index = m.collision_index)
    GROUP BY t.count_point_id
)
SELECT cp.count_point_id::text, cp.road_category, coalesce(d.dual_share, 0) >= 0.5,
       (SELECT count(*) FROM geo.junction j WHERE ST_DWithin(j.match_geom, cp.mid, %(r)s)),
       cp.length_km, cp.aadf, coalesce(n.n, 0), coalesce(n.ksi, 0), coalesce(n.fatal, 0),
       {_AUTHORITY.format(geom="cp.mid")}, cp.mid
FROM cp LEFT JOIN dual d USING (count_point_id) LEFT JOIN n USING (count_point_id)
"""

# Junctions whose major arms are all counted; exposure = vehicles entering. Uncounted minor
# arms get a typical flow for their class (``safety.typical_minor_flows``), from the counted
# minor arms of these same junctions.
_JUNCTIONS = f"""
WITH arms AS (
    SELECT a.junction_id, coalesce(sum(c.aadf), 0) / 2 AS entering,
           bool_or(a.role = 'major' AND c.aadf IS NULL) AS major_missing,
           array_agg(a.road_class) FILTER (WHERE a.role = 'minor' AND c.aadf IS NULL)
               AS uncounted,
           array_agg(a.road_class) FILTER (WHERE a.role = 'minor' AND c.aadf IS NOT NULL)
               AS counted_class,
           array_agg(c.aadf) FILTER (WHERE a.role = 'minor' AND c.aadf IS NOT NULL)
               AS counted_aadf
    FROM geo.junction_arm a LEFT JOIN cp_aadf c USING (count_point_id)
    GROUP BY a.junction_id
), n AS (
    SELECT jc.junction_id, count(*) AS n, count(*) FILTER (WHERE c.collision_severity < 3) AS ksi,
           count(*) FILTER (WHERE c.collision_severity = 1) AS fatal
    FROM geo.junction_collision jc JOIN core.collision c USING (collision_index)
    WHERE c.collision_year BETWEEN %(y0)s AND %(y1)s
    GROUP BY jc.junction_id
)
SELECT j.id, j.kind, j.signalised,
       (SELECT count(*) FROM geo.junction k WHERE ST_DWithin(k.match_geom, j.geom_bng, %(r)s)),
       a.entering, a.uncounted, a.counted_class, a.counted_aadf,
       coalesce(n.n, 0), coalesce(n.ksi, 0), coalesce(n.fatal, 0),
       {_AUTHORITY.format(geom="j.geom_bng")}, j.geom_bng
FROM geo.junction j
JOIN arms a ON a.junction_id = j.id
LEFT JOIN n ON n.junction_id = j.id
WHERE NOT a.major_missing
"""


def _links(conn: psycopg.Connection, params: dict) -> list[dict]:
    out = []
    rows = conn.execute(_LINKS, params)
    for cp, category, dual, density, length_km, aadf, n, ksi, fatal, authority, geom in rows:
        urban = sf.is_urban(density)
        region = sf.region_of(authority)
        out.append(
            {
                "unit_type": "link",
                "unit_id": cp,
                "family": sf.link_family(category, dual, urban),
                "urban": urban,
                "observed": n,
                "ksi": ksi,
                "fatal": fatal,
                "length_km": length_km,
                "flow": aadf,
                "flow_estimated": None,
                "flag": None,
                "region": region,
                "features": {"log_flow": math.log(aadf)} | sf.region_features(region),
                "offset": math.log(length_km),
                "geom": geom,
            }
        )
    return out


def _junctions(conn: psycopg.Connection, params: dict) -> list[dict]:
    rows = conn.execute(_JUNCTIONS, params).fetchall()
    urban = [sf.is_urban(r[3]) for r in rows]
    typical = sf.typical_minor_flows(
        (cls, u, aadf)
        for r, u in zip(rows, urban, strict=True)
        for cls, aadf in zip(r[6] or [], r[7] or [], strict=True)
    )
    out = []
    for row, is_urban in zip(rows, urban, strict=True):
        jid, kind, signalised, _, counted, uncounted, _, _, n, ksi, fatal, authority, geom = row
        estimated = sum(typical(cls, is_urban) for cls in uncounted or []) / 2
        entering = counted + estimated
        if entering <= 0:
            continue
        region = sf.region_of(authority)
        out.append(
            {
                "unit_type": "junction",
                "unit_id": jid,
                "family": sf.junction_family(kind, signalised, is_urban),
                "urban": is_urban,
                "observed": n,
                "ksi": ksi,
                "fatal": fatal,
                "length_km": None,
                "flow": entering,
                "flow_estimated": estimated or None,
                "flag": "minor_uncounted" if uncounted else None,
                "region": region,
                "features": {
                    "log_flow": math.log(entering),
                    "minor_uncounted": 1.0 if uncounted else 0.0,
                }
                | sf.region_features(region),
                "offset": 0.0,
                "geom": geom,
            }
        )
    return out


def _score(units: list[dict]) -> tuple[list[tuple], list[tuple]]:
    """Fit a model per peer group, then EB for every site. Returns (unit rows, model rows)."""
    groups = sf.assign_groups([u["family"] for u in units])
    by_group: dict[str, list[dict]] = defaultdict(list)
    for unit, group in zip(units, groups, strict=True):
        by_group[f"{unit['unit_type']}:{group}"].append(unit | {"group": group})
    unit_rows, model_rows = [], []
    for key, members in sorted(by_group.items()):
        spf = _fit(key, members)
        if spf is not None:
            model_rows.append(_model_row(key, spf, members))
        scored = []
        for u in members:
            predicted = eb = excess = None
            if spf is not None:
                predicted = spf.predict(u["features"], u["offset"])
                eb, excess, _ = sf.empirical_bayes(u["observed"], predicted, spf.alpha)
            scored.append((u, predicted, eb, excess))
        # Rank among similar sites in the same region: absolute excess grows with the
        # collisions a region records, so a national rank would still favour London.
        rank: dict[int, int] = {}
        size: dict[str, int] = defaultdict(int)
        for region in {u["region"] for u in members}:
            ranked = sorted(
                (s for s in scored if s[3] is not None and s[0]["region"] == region),
                key=lambda s: -s[3],
            )
            rank |= {id(s[0]): i for i, s in enumerate(ranked, start=1)}
            size[region] = len(ranked)
        for u, predicted, eb, excess in scored:
            unit_rows.append(
                (
                    u["unit_type"],
                    u["unit_id"],
                    u["group"],
                    "/".join(u["family"]),
                    u["urban"],
                    u["region"],
                    u["observed"],
                    u["ksi"],
                    u["fatal"],
                    predicted,
                    eb,
                    excess,
                    excess / u["length_km"] if excess is not None and u["length_km"] else None,
                    rank.get(id(u)),
                    size[u["region"]],
                    u["length_km"],
                    u["flow"],
                    u["flow_estimated"],
                    u["flag"],
                    u["geom"],
                )
            )
    return unit_rows, model_rows


def _fit(key: str, members: list[dict]) -> sf.Spf | None:
    if len(members) < MIN_FIT_SIZE:
        log.info("safety: %s has %s sites, too few to fit", key, len(members))
        return None
    features = [u["features"] for u in members]
    if len({tuple(f.values()) for f in features}) < 3:
        return None
    # A flag that never varies in the group can't be estimated: drop it. A region with only a
    # handful of sites in the group would just fit those sites: they share the baseline.
    varying = [k for k in features[0] if len({f[k] for f in features}) > 1]
    varying = [
        k
        for k in varying
        if not k.startswith("region_") or sum(f[k] for f in features) >= sf.MIN_REGION_SITES
    ]
    try:
        return sf.fit_spf(
            [u["observed"] for u in members],
            [{k: f[k] for k in varying} for f in features],
            [u["offset"] for u in members],
        )
    except (ValueError, ArithmeticError, np.linalg.LinAlgError) as exc:
        log.warning("safety: model for %s failed to fit: %s", key, exc)
        return None


def _model_row(key: str, spf: sf.Spf, members: list[dict]) -> tuple:
    """The fitted model plus the group's severity totals (for valuing its collisions)."""
    unit_type, group = key.split(":", 1)
    return (
        unit_type,
        group,
        spf.n,
        spf.intercept,
        json.dumps(spf.coefficients),
        spf.alpha,
        spf.mean_observed,
        sum(u["observed"] for u in members),
        sum(u["ksi"] for u in members),
        sum(u["fatal"] for u in members),
    )


_DDL = {
    "safety_unit": """CREATE TABLE geo.safety_unit__new (
        unit_type text NOT NULL, unit_id text NOT NULL, peer_group text NOT NULL,
        family text NOT NULL, urban boolean, region text, observed integer NOT NULL, ksi integer,
        fatal integer, predicted double precision, eb double precision, excess double precision,
        excess_per_km double precision, excess_rank integer, group_size integer,
        length_km double precision, flow double precision, flow_estimated double precision,
        flag text, geom_bng geometry(Point, 27700))""",
    "safety_model": """CREATE TABLE geo.safety_model__new (
        unit_type text NOT NULL, peer_group text NOT NULL, n integer NOT NULL,
        intercept double precision, coefficients jsonb, alpha double precision,
        mean_observed double precision, observed_total integer, ksi_total integer,
        fatal_total integer)""",
    "safety_calibration": cal.DDL,
}
UNIT_COLUMNS = (
    "unit_type, unit_id, peer_group, family, urban, region, observed, ksi, fatal, predicted, eb, "
    "excess, excess_per_km, excess_rank, group_size, length_km, flow, flow_estimated, flag, "
    "geom_bng"
)
_MODEL_COLUMNS = (
    "unit_type, peer_group, n, intercept, coefficients, alpha, mean_observed, "
    "observed_total, ksi_total, fatal_total"
)


def _copy(conn: psycopg.Connection, table: str, columns: str, rows: list[tuple]) -> None:
    with conn.cursor() as cur, cur.copy(f"COPY geo.{table}__new ({columns}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


def score_period(conn: psycopg.Connection, y0: int, y1: int) -> tuple[list[tuple], list[tuple]]:
    """Fit and score every site on collisions and flows from years y0-y1 (no writes).

    The build uses the latest five years; the out-of-sample check (safety_check) scores an
    earlier period the same way.
    """
    params = {"y0": y0, "y1": y1, "r": _DENSITY_RADIUS_M}
    with conn.transaction():
        # ON COMMIT DROP doesn't fire inside an outer transaction: clear a previous period's
        conn.execute("DROP TABLE IF EXISTS cp_aadf")
        conn.execute(_CP_AADF, params)
        units = _links(conn, params) + _junctions(conn, params)
    return _score(units)


def build_safety(conn: psycopg.Connection) -> None:
    needed = (
        "core.collision",
        "geo.traffic_aadf",
        "geo.traffic_stretch",
        "geo.collision_link",
        "geo.junction_collision",
        "geo.junction_arm",
    )
    if not tables_exist(conn, *needed):
        log.info("safety skipped: needs traffic, the road network and both collision matches")
        return
    latest = conn.execute("SELECT max(collision_year) FROM core.collision").fetchone()[0]
    if latest is None:
        return
    y0, y1 = latest - SAFETY_YEARS + 1, latest
    unit_rows, model_rows = score_period(conn, y0, y1)
    years = range(latest - COLLISION_YEARS + 1, latest + 1)
    calibration = cal.calibration_rows(
        ((r[0], r[1], r[2], r[9]) for r in unit_rows),
        cal.yearly_counts(conn, years.start, years.stop - 1),
        years,
        SAFETY_YEARS,
    )
    with conn.transaction():
        for table, ddl in _DDL.items():
            conn.execute(f"DROP TABLE IF EXISTS geo.{table}__new")
            conn.execute(ddl)
        _copy(conn, "safety_unit", UNIT_COLUMNS, unit_rows)
        _copy(conn, "safety_model", _MODEL_COLUMNS, model_rows)
        _copy(conn, "safety_calibration", cal.COLUMNS, calibration)
    scored = sum(r[9] is not None for r in unit_rows)
    swap_tables(
        conn,
        "safety",
        {
            "safety_unit": [
                "ALTER TABLE geo.safety_unit ADD PRIMARY KEY (unit_type, unit_id)",
                "CREATE INDEX safety_unit_geom_idx ON geo.safety_unit USING gist (geom_bng)",
            ],
            "safety_model": [
                "ALTER TABLE geo.safety_model ADD PRIMARY KEY (unit_type, peer_group)"
            ],
            "safety_calibration": cal.INDEXES,
        },
        f"SPF + Empirical Bayes, {y0}-{y1}",
        len(unit_rows),
        f"{scored:,} sites scored in {len(model_rows)} peer groups ({y0}-{y1})",
    )
