"""Atomic swap of freshly loaded geo.<table>__new tables into place."""

from __future__ import annotations

import logging

import psycopg
from psycopg.rows import tuple_row

log = logging.getLogger(__name__)


def tables_exist(conn: psycopg.Connection, *tables: str) -> bool:
    """Whether every geo/core table named (schema-qualified) exists."""
    with conn.cursor(row_factory=tuple_row) as cur:  # API connections return dict rows
        cur.execute(
            "SELECT bool_and(to_regclass(t) IS NOT NULL) FROM unnest(%s::text[]) AS t",
            (list(tables),),
        )
        return bool(cur.fetchone()[0])


def swap_tables(
    conn: psycopg.Connection,
    dataset: str,
    tables: dict[str, list[str]],
    source: str,
    rows: int,
    detail: str | None = None,
) -> None:
    """Swap each geo.<table>__new in (running its DDL) and log the dataset, atomically."""
    with conn.transaction():
        for table, ddl_after in tables.items():
            conn.execute(f"DROP TABLE IF EXISTS geo.{table}")
            conn.execute(f"ALTER TABLE geo.{table}__new RENAME TO {table}")
            for stmt in ddl_after:
                conn.execute(stmt)
        conn.execute(
            """INSERT INTO geo.reference_refresh (dataset, refreshed_at, source, row_count, detail)
               VALUES (%s, clock_timestamp(), %s, %s, %s)
               ON CONFLICT (dataset) DO UPDATE SET refreshed_at = clock_timestamp(),
                   source = EXCLUDED.source, row_count = EXCLUDED.row_count,
                   detail = EXCLUDED.detail""",
            (dataset, source, rows, detail),
        )
    for table in tables:
        conn.execute(f"ANALYZE geo.{table}")
    conn.commit()
    log.info("geo dataset %s refreshed: %s rows", dataset, f"{rows:,}")
