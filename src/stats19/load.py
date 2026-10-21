"""Stream a CSV into raw.<table> (all TEXT columns, header-driven) with COPY."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg import sql

from stats19.columns import HeaderCheck, TableSpec, check_header, normalise_header

log = logging.getLogger(__name__)

COPY_CHUNK_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class RawLoad:
    table_name: str
    columns: tuple[str, ...]
    row_count: int
    header: HeaderCheck


def read_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return next(csv.reader(f))


def load_raw(conn: psycopg.Connection, spec: TableSpec, path: Path) -> RawLoad:
    columns = normalise_header(read_header(path))
    if len(set(columns)) != len(columns):
        raise ValueError(f"{path.name}: duplicate column names in header")
    header = check_header(spec, columns)
    if header.unexpected:
        log.warning("%s: unexpected columns kept in raw only: %s", spec.name, header.unexpected)

    table = sql.Identifier("raw", spec.name)
    col_defs = sql.SQL(", ").join(sql.SQL("{} text").format(sql.Identifier(c)) for c in columns)
    col_list = sql.SQL(", ").join(sql.Identifier(c) for c in columns)

    with conn.transaction():
        conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
        conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(table))
        conn.execute(sql.SQL("CREATE UNLOGGED TABLE {} ({})").format(table, col_defs))
        copy_sql = sql.SQL(
            "COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')"
        ).format(table, col_list)
        with conn.cursor() as cur:
            with cur.copy(copy_sql) as copy, path.open("rb") as f:
                while chunk := f.read(COPY_CHUNK_BYTES):
                    copy.write(chunk)
            row_count = cur.rowcount

    log.info("raw.%s: %s rows", spec.name, f"{row_count:,}")
    return RawLoad(spec.name, tuple(columns), row_count, header)
