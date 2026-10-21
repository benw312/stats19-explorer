"""Validation gates run against schema "build" before it replaces "core".

Any failed check with severity 'error' blocks the swap. Thresholds were
set from the first real full loads (FU-007).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import psycopg
from psycopg import sql

from stats19.columns import (
    TABLES,
    Kind,
    TableSpec,
    parse_failure_exprs,
    unmatched_guide_fields,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Thresholds:
    # Set from the first two full loads (FU-007): 0 quarantined rows after FU-008,
    # 0 parse failures, identical row counts. Small margins allow for DfT revisions.
    max_quarantine_ratio: float = 0.001
    min_row_ratio_vs_previous: float = 0.99
    max_parse_failure_ratio: float = 0.0001
    first_year: int = 1979


DEFAULT_THRESHOLDS = Thresholds()


@dataclass(frozen=True)
class CheckResult:
    check_name: str
    table_name: str
    severity: str
    passed: bool
    observed: float | None = None
    threshold: float | None = None
    detail: str | None = None


def _scalar(conn: psycopg.Connection, query: str | sql.Composable, params=None):
    return conn.execute(query, params).fetchone()[0]


def _ratio(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def check_row_counts(conn, previous: dict[str, int], t: Thresholds) -> list[CheckResult]:
    out = []
    for name in TABLES:
        n = _scalar(conn, sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier("build", name)))
        out.append(CheckResult("core_row_count", name, "error", n > 0, n, 1))
        if name in previous:
            ratio = _ratio(n, previous[name])
            out.append(
                CheckResult(
                    "row_count_vs_previous",
                    name,
                    "error",
                    ratio >= t.min_row_ratio_vs_previous,
                    ratio,
                    t.min_row_ratio_vs_previous,
                    f"previous={previous[name]} now={n}",
                )
            )
    return out


def check_quarantine(conn, typed_counts: dict[str, int], t: Thresholds) -> list[CheckResult]:
    rows = conn.execute(
        "SELECT table_name, reason, count(*) FROM build.quarantine GROUP BY 1, 2"
    ).fetchall()
    out = []
    for name in TABLES:
        rejected = {r: n for tbl, r, n in rows if tbl == name and r != "orphan_vehicle_unlinked"}
        ratio = _ratio(sum(rejected.values()), typed_counts.get(name, 0))
        detail = ", ".join(f"{r}={n}" for r, n in sorted(rejected.items())) or None
        out.append(
            CheckResult(
                "quarantine_ratio",
                name,
                "error",
                ratio <= t.max_quarantine_ratio,
                ratio,
                t.max_quarantine_ratio,
                detail,
            )
        )
    unlinked = sum(n for tbl, r, n in rows if r == "orphan_vehicle_unlinked")
    out.append(
        CheckResult("casualty_vehicle_unlinked", "casualty", "warn", unlinked == 0, unlinked, 0)
    )
    return out


def check_parse_failures(
    conn, spec: TableSpec, available: set[str], raw_rows: int, t: Thresholds
) -> CheckResult:
    exprs = parse_failure_exprs(spec, available)
    if not exprs:
        return CheckResult("parse_failures", spec.name, "error", True, 0, 0)
    sums = ", ".join(f"count(*) FILTER (WHERE {expr})" for _, expr in exprs)
    counts = conn.execute(f"SELECT {sums} FROM raw.{spec.name} r").fetchone()
    failures = {col: n for (col, _), n in zip(exprs, counts, strict=True) if n}
    worst = max(failures.values(), default=0)
    ratio = _ratio(worst, raw_rows)
    detail = ", ".join(f"{c}={n}" for c, n in sorted(failures.items(), key=lambda x: -x[1]))
    return CheckResult(
        "parse_failures",
        spec.name,
        "error",
        ratio <= t.max_parse_failure_ratio,
        ratio,
        t.max_parse_failure_ratio,
        detail or None,
    )


def check_guide_fields(conn) -> CheckResult:
    """Warn when the data guide documents a field we have no column for (FU-002)."""
    pairs = conn.execute(
        """SELECT table_name, field_name FROM build.lookup_code WHERE source = 'dft_guide'
           UNION SELECT table_name, field_name FROM build.lookup_field_note"""
    ).fetchall()
    unmatched = unmatched_guide_fields(pairs)
    detail = ", ".join(f"{t}.{f}" for t, f in unmatched)
    return CheckResult(
        "guide_field_unmatched", "", "warn", not unmatched, len(unmatched), 0, detail or None
    )


def check_marts(conn) -> list[CheckResult]:
    """mart row counts match core; catalogue covers the spec; road-user codes all grouped."""
    core_n, mart_n = conn.execute(
        """SELECT (SELECT count(*) FROM build.collision),
                  (SELECT count(*) FROM build_mart.collision_summary)"""
    ).fetchone()
    expected_fields = sum(len(spec.columns) for spec in TABLES.values())
    catalog_n = _scalar(conn, "SELECT count(*) FROM build_mart.field_catalog")
    unmapped = conn.execute(
        """SELECT src, code, n FROM (
               SELECT 'vehicle.vehicle_type' AS src, vehicle_type AS code, count(*) AS n
               FROM build.vehicle GROUP BY 2
               UNION ALL
               SELECT 'casualty.casualty_type', casualty_type, count(*)
               FROM build.casualty GROUP BY 2) x
           WHERE code IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM build_mart.road_user_group g WHERE g.code = x.code)
           ORDER BY n DESC"""
    ).fetchall()
    detail = ", ".join(f"{src}={code} ({n})" for src, code, n in unmapped)
    return [
        CheckResult("mart_collision_rows", "collision", "error", mart_n == core_n, mart_n, core_n),
        CheckResult(
            "field_catalog_complete",
            "",
            "error",
            catalog_n == expected_fields,
            catalog_n,
            expected_fields,
        ),
        CheckResult(
            "road_user_group_unmapped", "", "warn", not unmapped, len(unmapped), 0, detail or None
        ),
    ]


def check_year_coverage(conn, t: Thresholds) -> CheckResult:
    missing = [
        r[0]
        for r in conn.execute(
            """SELECT y FROM generate_series(
                   %s::int, (SELECT max(collision_year)::int FROM build.collision)) y
               WHERE NOT EXISTS (SELECT 1 FROM build.collision WHERE collision_year = y)""",
            (t.first_year,),
        )
    ]
    return CheckResult(
        "year_coverage",
        "collision",
        "error",
        not missing,
        len(missing),
        0,
        f"missing years: {missing}" if missing else None,
    )


def check_reused_casualty_references(conn) -> CheckResult:
    """Informational: casualties kept despite sharing a casualty_reference (FU-008)."""
    n = _scalar(conn, "SELECT count(*) FROM build.casualty WHERE is_reference_reused")
    return CheckResult("casualty_reference_reused", "casualty", "info", True, n, None)


def check_geometry(conn) -> CheckResult:
    total, missing = conn.execute(
        "SELECT count(*), count(*) FILTER (WHERE geom_wgs84 IS NULL) FROM build.collision"
    ).fetchone()
    ratio = _ratio(missing, total)
    return CheckResult("geometry_missing", "collision", "warn", missing == 0, ratio, 0)


def check_child_counts(conn) -> list[CheckResult]:
    out = []
    for child, column in (("vehicle", "number_of_vehicles"), ("casualty", "number_of_casualties")):
        total, mismatched = conn.execute(
            sql.SQL(
                """SELECT count(*), count(*) FILTER (WHERE c.{col} IS DISTINCT FROM k.n)
                   FROM build.collision c
                   LEFT JOIN (SELECT collision_index, count(*) AS n FROM {child}
                              GROUP BY 1) k USING (collision_index)"""
            ).format(col=sql.Identifier(column), child=sql.Identifier("build", child))
        ).fetchone()
        out.append(
            CheckResult(
                f"{column}_mismatch",
                "collision",
                "warn",
                mismatched == 0,
                _ratio(mismatched, total),
                0,
            )
        )
    return out


def check_unlabelled_codes(conn, spec: TableSpec) -> CheckResult:
    code_cols = [c.name for c in spec.columns if c.kind is Kind.CODE]
    values = ", ".join(f"('{c}', t.{c}::text)" for c in code_cols)
    rows = conn.execute(
        f"""SELECT x.field, x.code, count(*) AS n
            FROM build.{spec.name} t
            CROSS JOIN LATERAL (VALUES {values}) AS x(field, code)
            WHERE x.code IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM build.lookup_code l
                  WHERE l.table_name = %s AND l.field_name = x.field AND l.code = x.code)
            GROUP BY 1, 2 ORDER BY n DESC""",
        (spec.name,),
    ).fetchall()
    detail = ", ".join(f"{f}={c} ({n})" for f, c, n in rows[:20])
    return CheckResult(
        "unlabelled_codes", spec.name, "warn", not rows, len(rows), 0, detail or None
    )


def run_checks(
    conn: psycopg.Connection,
    raw_columns: dict[str, set[str]],
    raw_rows: dict[str, int],
    typed_counts: dict[str, int],
    previous_counts: dict[str, int],
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> list[CheckResult]:
    results = check_row_counts(conn, previous_counts, thresholds)
    results += check_quarantine(conn, typed_counts, thresholds)
    for name, spec in TABLES.items():
        results.append(
            check_parse_failures(conn, spec, raw_columns[name], raw_rows[name], thresholds)
        )
        results.append(check_unlabelled_codes(conn, spec))
    results.append(check_guide_fields(conn))
    results.append(check_year_coverage(conn, thresholds))
    results.append(check_reused_casualty_references(conn))
    results.append(check_geometry(conn))
    results += check_child_counts(conn)
    results += check_marts(conn)
    conn.commit()
    for r in results:
        level = (
            logging.INFO
            if r.passed
            else (logging.ERROR if r.severity == "error" else logging.WARNING)
        )
        log.log(
            level,
            "check %-28s %-9s passed=%s observed=%s %s",
            r.check_name,
            r.table_name,
            r.passed,
            r.observed,
            r.detail or "",
        )
    return results


def blocking_failures(results: list[CheckResult]) -> list[CheckResult]:
    return [r for r in results if r.severity == "error" and not r.passed]
