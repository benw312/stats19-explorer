"""Analysis-ready layer: built in schema build_mart, swapped in as mart with core.

Everything here is decoded or counted from recorded fields. Nothing is inferred
(see FU-001). Views in build_mart reference build.* tables by OID, so they keep
pointing at the right tables when both schemas are renamed in the swap.
"""

from __future__ import annotations

import json
import logging

import psycopg

from stats19.columns import TABLES, Kind, TableSpec, core_name

log = logging.getLogger(__name__)

# vehicle_type / casualty_type codes grouped by road user. The codes are shared by
# both fields; era-specific codes (1979-2004, 1xx) sit with their modern equivalents.
ROAD_USER_GROUPS: dict[str, tuple[int, ...]] = {
    "pedestrian": (0,),
    "pedal_cycle": (1,),
    "motorcycle": (2, 3, 4, 5, 23, 97, 103, 104, 105, 106),
    "car": (8, 9, 108, 109),
    "bus": (10, 11, 110),
    "goods_light": (19,),
    "goods_heavy": (20, 21, 113),
    "goods_unknown": (98,),
    "ppt": (33,),
    "mobility_scooter": (22,),
    "horse": (16,),
    "other": (17, 18, 90),
    "unknown": (-1, 99),
}
VEHICLE_GROUPS = tuple(g for g in ROAD_USER_GROUPS if g != "pedestrian")
INVOLVES_GROUPS = (
    "pedal_cycle",
    "motorcycle",
    "bus",
    "goods_heavy",
    "ppt",
    "mobility_scooter",
    "horse",
)

_CODE_TO_GROUP = {code: g for g, codes in ROAD_USER_GROUPS.items() for code in codes}


def group_for_code(code: int) -> str | None:
    return _CODE_TO_GROUP.get(code)


# ------------------------------------------------------------------ SQL generation


def _code_columns(spec: TableSpec) -> list[str]:
    return [c.name for c in spec.columns if c.kind is Kind.CODE]


def _label_joins(spec: TableSpec, alias: str) -> tuple[str, str]:
    """(select-list of <field>_label columns, LEFT JOIN clauses) for every code column."""
    selects, joins = [], []
    for i, col in enumerate(_code_columns(spec)):
        lk = f"l{i}"
        selects.append(f"{lk}.label AS {col}_label")
        joins.append(
            f"LEFT JOIN build.lookup_code {lk} ON {lk}.table_name = '{spec.name}' "
            f"AND {lk}.field_name = '{col}' AND {lk}.code = {alias}.{col}::text"
        )
    return ",\n       ".join(selects), "\n".join(joins)


def collision_summary_sql() -> str:
    cas_groups = ",\n           ".join(
        f"count(*) FILTER (WHERE g.road_user_group = '{g}') AS n_casualties_{g}"
        for g in ROAD_USER_GROUPS
    )
    veh_groups = ",\n           ".join(
        f"count(*) FILTER (WHERE g.road_user_group = '{g}') AS n_vehicles_{g}"
        for g in VEHICLE_GROUPS
    )
    # Per-collision counts fit in smallint; bigint (count's type) tripled the table size.
    out_cas = ",\n       ".join(
        f"coalesce(k.n_casualties_{g}, 0)::smallint AS n_casualties_{g}" for g in ROAD_USER_GROUPS
    )
    out_veh = ",\n       ".join(
        f"coalesce(v.n_vehicles_{g}, 0)::smallint AS n_vehicles_{g}" for g in VEHICLE_GROUPS
    )
    involves = ",\n       ".join(
        f"coalesce(v.n_vehicles_{g}, 0) > 0 AS involves_{g}" for g in INVOLVES_GROUPS
    )
    return f"""
CREATE TABLE build_mart.collision_summary AS
WITH k AS (
    SELECT k.collision_index,
           count(*) AS n_casualties,
           count(*) FILTER (WHERE k.casualty_severity = 1) AS n_fatal,
           count(*) FILTER (WHERE k.casualty_severity = 2) AS n_serious,
           count(*) FILTER (WHERE k.casualty_severity = 3) AS n_slight,
           sum(k.casualty_adjusted_severity_serious) AS adjusted_serious,
           sum(k.casualty_adjusted_severity_slight) AS adjusted_slight,
           bool_or(k.casualty_class = 3) AS has_pedestrian_casualty,
           {cas_groups}
    FROM build.casualty k
    LEFT JOIN build_mart.road_user_group g ON g.code = k.casualty_type
    GROUP BY k.collision_index
), v AS (
    SELECT v.collision_index,
           min(v.age_of_driver) AS youngest_driver_age,
           max(v.age_of_driver) AS oldest_driver_age,
           {veh_groups}
    FROM build.vehicle v
    LEFT JOIN build_mart.road_user_group g ON g.code = v.vehicle_type
    GROUP BY v.collision_index
)
SELECT c.collision_index,
       coalesce(k.n_casualties, 0)::smallint AS n_casualties,
       coalesce(k.n_fatal, 0)::smallint AS n_fatal,
       coalesce(k.n_serious, 0)::smallint AS n_serious,
       coalesce(k.n_slight, 0)::smallint AS n_slight,
       k.adjusted_serious,
       k.adjusted_slight,
       coalesce(k.has_pedestrian_casualty, false) AS has_pedestrian_casualty,
       {out_cas},
       {out_veh},
       {involves},
       v.youngest_driver_age::smallint AS youngest_driver_age,
       v.oldest_driver_age::smallint AS oldest_driver_age
FROM build.collision c
LEFT JOIN k USING (collision_index)
LEFT JOIN v USING (collision_index);

ALTER TABLE build_mart.collision_summary ADD PRIMARY KEY (collision_index);
"""


def views_sql() -> str:
    col = TABLES["collision"]
    veh = TABLES["vehicle"]
    cas = TABLES["casualty"]
    c_sel, c_join = _label_joins(col, "m")
    v_sel, v_join = _label_joins(veh, "t")
    k_sel, k_join = _label_joins(cas, "t")
    return f"""
CREATE VIEW build_mart.collision AS
SELECT * FROM build.collision c
JOIN build_mart.collision_summary s USING (collision_index);

CREATE VIEW build_mart.collision_decoded AS
SELECT m.*,
       {c_sel}
FROM build_mart.collision m
{c_join};

CREATE VIEW build_mart.vehicle_decoded AS
SELECT t.*, g.road_user_group,
       {v_sel}
FROM build.vehicle t
LEFT JOIN build_mart.road_user_group g ON g.code = t.vehicle_type
{v_join};

CREATE VIEW build_mart.casualty_decoded AS
SELECT t.*, g.road_user_group,
       {k_sel}
FROM build.casualty t
LEFT JOIN build_mart.road_user_group g ON g.code = t.casualty_type
{k_join};
"""


def code_counts_sql(spec: TableSpec, source: str = "build") -> str:
    """Rows per field x year x code. One scan with GROUPING SETS (one hash aggregate per
    field) is ~2x faster than unpivoting every row with LATERAL VALUES (FU-012)."""
    cols = _code_columns(spec)
    sets = ", ".join(f"(t.collision_year, t.{c})" for c in cols)
    # GROUPING(col) = 0 marks the set the row belongs to.
    field = "CASE " + " ".join(f"WHEN GROUPING(t.{c}) = 0 THEN '{c}'" for c in cols) + " END"
    in_set = (f"CASE WHEN GROUPING(t.{c}) = 0 THEN t.{c} END" for c in cols)
    code = "COALESCE(" + ", ".join(in_set) + ")"
    return f"""
INSERT INTO build_mart.code_counts
SELECT '{spec.name}', x.field_name, x.collision_year, x.code, l.label, x.n
FROM (
    SELECT {field} AS field_name, t.collision_year, {code} AS code, count(*) AS n
    FROM {source}.{spec.name} t
    GROUP BY GROUPING SETS ({sets})
) x
LEFT JOIN {source}.lookup_code l
  ON l.table_name = '{spec.name}' AND l.field_name = x.field_name AND l.code = x.code::text
WHERE x.code IS NOT NULL;
"""


# Web Mercator cell sizes (m) matching the tile bin size at zoom 8 and 10 (32 bins/tile).
WEB_MERCATOR_WIDTH = 40075016.68557849
GRID_LEVELS = {8: WEB_MERCATOR_WIDTH / 2**8 / 32, 10: WEB_MERCATOR_WIDTH / 2**10 / 32}


def collision_grid_sql() -> str:
    """Counts per (grid level, year, severity, cell) for fast zoomed-out map tiles."""
    levels = ", ".join(f"({lvl}, {size!r})" for lvl, size in GRID_LEVELS.items())
    indexes = "\n".join(
        f"CREATE INDEX collision_grid_l{lvl}_idx ON build_mart.collision_grid "
        f"USING gist (cell) WHERE lvl = {lvl};"
        for lvl in GRID_LEVELS
    )
    return f"""
CREATE TABLE build_mart.collision_grid AS
SELECT l.lvl::smallint AS lvl, c.collision_year, c.collision_severity,
       ST_SnapToGrid(c.geom_3857, l.size) AS cell,
       count(*)::integer AS n,
       sum(ST_X(c.geom_3857)) AS sum_x, sum(ST_Y(c.geom_3857)) AS sum_y
FROM build.collision c
CROSS JOIN (VALUES {levels}) AS l(lvl, size)
WHERE c.geom_3857 IS NOT NULL
GROUP BY 1, 2, 3, 4;
{indexes}
"""


# ------------------------------------------------------------------ field catalogue


def _populated_expr(name: str, kind: Kind) -> str:
    if kind is Kind.CODE:
        return f"{name} IS NOT NULL AND {name} <> -1"
    return f"{name} IS NOT NULL"


def harmonisation_note(spec: TableSpec, field: str) -> str | None:
    names = spec.names
    if field.endswith("_historic"):
        base = field.removesuffix("_historic")
        # the two pedestrian crossing fields were merged into one in 2024
        current = "pedestrian_crossing" if base.startswith("pedestrian_crossing_") else base
        return (
            f"2011-specification coding with pre-2024 detail; use {current} "
            "for analysis across years"
        )
    if any(
        n.endswith("_historic")
        and (n.removesuffix("_historic") == field or n.startswith(f"{field}_"))
        for n in names
    ):
        return (
            "2024-specification coding, back-filled by DfT for all earlier years "
            "(verified consistent with the conversion table, PLAN-003)"
        )
    return None


def _catalog_rows(conn: psycopg.Connection, spec: TableSpec) -> list[tuple]:
    counts = ", ".join(
        f"count(*) FILTER (WHERE {_populated_expr(core_name(spec.name, c.name), c.kind)})"
        for c in spec.columns
    )
    by_year = conn.execute(
        f"SELECT collision_year, count(*), {counts} FROM build.{spec.name} "
        "WHERE collision_year IS NOT NULL GROUP BY 1 ORDER BY 1"
    ).fetchall()
    notes = dict(
        conn.execute(
            """SELECT field_name, string_agg(note, ' ') FROM build.lookup_field_note
               WHERE table_name = %s GROUP BY 1""",
            (spec.name,),
        ).fetchall()
    )
    labelled = {
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT field_name FROM build.lookup_code WHERE table_name = %s",
            (spec.name,),
        )
    }
    rows = []
    for i, col in enumerate(spec.columns):
        pct = {
            str(year): round(100.0 * vals[i] / total, 1) if total else 0.0
            for year, total, *vals in by_year
        }
        years = [year for year, _total, *vals in by_year if vals[i] > 0]
        rows.append(
            (
                spec.name,
                core_name(spec.name, col.name),
                col.kind.value,
                col.kind.sql_type,
                notes.get(col.name),
                min(years) if years else None,
                max(years) if years else None,
                json.dumps(pct),
                col.name in labelled,
                harmonisation_note(spec, col.name),
            )
        )
    return rows


def build_field_catalog(conn: psycopg.Connection) -> None:
    conn.execute(
        """CREATE TABLE build_mart.field_catalog (
               table_name            text NOT NULL,
               field_name            text NOT NULL,
               kind                  text NOT NULL,
               sql_type              text NOT NULL,
               description           text,
               first_year            smallint,
               last_year             smallint,
               populated_pct_by_year jsonb NOT NULL,
               is_labelled           boolean NOT NULL,
               harmonisation_note    text,
               PRIMARY KEY (table_name, field_name))"""
    )
    with conn.cursor() as cur:
        for spec in TABLES.values():
            cur.executemany(
                "INSERT INTO build_mart.field_catalog VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                _catalog_rows(conn, spec),
            )


# ------------------------------------------------------------------ orchestration


def build_marts(conn: psycopg.Connection) -> None:
    with conn.transaction():
        conn.execute("DROP SCHEMA IF EXISTS build_mart CASCADE")
        conn.execute("CREATE SCHEMA build_mart")
        conn.execute(
            """CREATE TABLE build_mart.road_user_group (
                   code smallint PRIMARY KEY, road_user_group text NOT NULL)"""
        )
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO build_mart.road_user_group VALUES (%s, %s)",
                sorted(_CODE_TO_GROUP.items()),
            )
        log.info("mart: collision_summary")
        conn.execute(collision_summary_sql())
        conn.execute(views_sql())
        log.info("mart: collision_grid")
        conn.execute(collision_grid_sql())
        log.info("mart: field_catalog")
        build_field_catalog(conn)
        log.info("mart: code_counts")
        conn.execute(
            """CREATE TABLE build_mart.code_counts (
                   table_name text NOT NULL, field_name text NOT NULL,
                   collision_year smallint NOT NULL, code smallint NOT NULL,
                   label text, n bigint NOT NULL,
                   PRIMARY KEY (table_name, field_name, collision_year, code))"""
        )
        for spec in TABLES.values():
            conn.execute(code_counts_sql(spec))
    conn.execute("ANALYZE build_mart.collision_summary")
    conn.execute("ANALYZE build_mart.collision_grid")
    conn.commit()
