"""Build the typed, keyed tables in schema "build" and swap it in as "core"."""

from __future__ import annotations

import logging

import psycopg
from psycopg import sql

from stats19.columns import TableSpec, typed_select_list
from stats19.db import read_sql
from stats19.guide import Guide, load_supplement, merge_supplement

log = logging.getLogger(__name__)


def reset_build(conn: psycopg.Connection) -> None:
    with conn.transaction():
        conn.execute("DROP SCHEMA IF EXISTS build_mart CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS build CASCADE")
        conn.execute("CREATE SCHEMA build")


def load_lookups(conn: psycopg.Connection, guide: Guide) -> None:
    with conn.transaction():
        conn.execute(
            """CREATE TABLE build.lookup_code (
                   table_name text NOT NULL,
                   field_name text NOT NULL,
                   code       text NOT NULL,
                   label      text NOT NULL,
                   note       text,
                   source     text NOT NULL CHECK (source IN ('dft_guide', 'supplement')),
                   PRIMARY KEY (table_name, field_name, code))"""
        )
        conn.execute(
            """CREATE TABLE build.lookup_field_note (
                   table_name text NOT NULL,
                   field_name text NOT NULL,
                   note       text NOT NULL)"""
        )
        conn.execute(
            """CREATE TABLE build.lookup_conversion (
                   table_name text NOT NULL,
                   old_field  text NOT NULL,
                   old_code   text NOT NULL,
                   old_label  text,
                   new_field  text NOT NULL,
                   new_code   text NOT NULL,
                   new_label  text)"""
        )
        with conn.cursor() as cur:
            with cur.copy("COPY build.lookup_code FROM STDIN") as copy:
                for c in merge_supplement(guide.codes, load_supplement()):
                    copy.write_row((c.table_name, c.field_name, c.code, c.label, c.note, c.source))
            with cur.copy("COPY build.lookup_field_note FROM STDIN") as copy:
                for row in guide.field_notes:
                    copy.write_row(row)
            with cur.copy("COPY build.lookup_conversion FROM STDIN") as copy:
                for v in guide.conversions:
                    copy.write_row(
                        (
                            v.table_name,
                            v.old_field,
                            v.old_code,
                            v.old_label,
                            v.new_field,
                            v.new_code,
                            v.new_label,
                        )
                    )
    log.info("lookups: %d codes, %d conversions", len(guide.codes), len(guide.conversions))


def build_typed(conn: psycopg.Connection, spec: TableSpec, available: set[str]) -> int:
    """raw.<t> -> build.<t>_typed with exact-duplicate rows collapsed. Returns row count."""
    query = sql.SQL(
        "CREATE UNLOGGED TABLE {target} AS SELECT DISTINCT\n    {cols}\nFROM {source} r"
    ).format(
        target=sql.Identifier("build", f"{spec.name}_typed"),
        cols=sql.SQL(typed_select_list(spec, available)),
        source=sql.Identifier("raw", spec.name),
    )
    with conn.transaction():
        cur = conn.execute(query)
    log.info("build.%s_typed: %s rows", spec.name, f"{cur.rowcount:,}")
    return cur.rowcount


def build_core(conn: psycopg.Connection) -> None:
    with conn.transaction():
        conn.execute(read_sql("build", "core.sql"))
        for name in ("collision", "vehicle", "casualty"):
            conn.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier("build", f"{name}_typed")))
    conn.execute("ANALYZE build.collision")
    conn.execute("ANALYZE build.vehicle")
    conn.execute("ANALYZE build.casualty")
    conn.commit()


def _schema_exists(conn: psycopg.Connection, name: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (name,)).fetchone())


def swap_in_build(conn: psycopg.Connection, keep_previous: bool = False) -> None:
    """Atomically replace core/mart with build/build_mart in one transaction (FU-005)."""
    pairs = (("core", "build"), ("mart", "build_mart"))
    with conn.transaction():
        for live, staged in pairs:
            conn.execute(f"DROP SCHEMA IF EXISTS {live}_previous CASCADE")
            if _schema_exists(conn, live):
                conn.execute(f"ALTER SCHEMA {live} RENAME TO {live}_previous")
            if _schema_exists(conn, staged):
                conn.execute(f"ALTER SCHEMA {staged} RENAME TO {live}")
    if not keep_previous:
        with conn.transaction():
            for live, _ in pairs:
                conn.execute(f"DROP SCHEMA IF EXISTS {live}_previous CASCADE")
    log.info("schemas build/build_mart swapped in as core/mart")
