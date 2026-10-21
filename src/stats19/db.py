"""Connection helpers and a minimal forward-only migration runner."""

from __future__ import annotations

import logging
from importlib import resources

import psycopg
import psycopg.sql

log = logging.getLogger(__name__)

_SQL_ROOT = resources.files("stats19") / "sql"


def read_sql(*parts: str) -> str:
    return _SQL_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url, autocommit=False)


def migrate(conn: psycopg.Connection, api_password: str | None = None) -> list[str]:
    """Apply any not-yet-applied files in sql/migrations, in name order; then let the API's
    read-only role log in when its password is configured (PLAN-006 C4)."""
    with conn.transaction():
        conn.execute("CREATE SCHEMA IF NOT EXISTS etl")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS etl.schema_migration (
                   filename text PRIMARY KEY,
                   applied_at timestamptz NOT NULL DEFAULT now())"""
        )
        applied = {r[0] for r in conn.execute("SELECT filename FROM etl.schema_migration")}

    files = sorted(
        f.name for f in _SQL_ROOT.joinpath("migrations").iterdir() if f.name.endswith(".sql")
    )
    newly_applied = []
    for name in files:
        if name in applied:
            continue
        log.info("applying migration %s", name)
        with conn.transaction():
            conn.execute(read_sql("migrations", name))
            conn.execute("INSERT INTO etl.schema_migration (filename) VALUES (%s)", (name,))
        newly_applied.append(name)
    if api_password:
        ensure_api_role(conn, api_password)
    return newly_applied


API_ROLE = "stats19_api"


def ensure_api_role(conn: psycopg.Connection, password: str) -> None:
    """Let the read-only API role (migration 004) log in with this password."""
    with conn.transaction():
        conn.execute(
            psycopg.sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                psycopg.sql.Identifier(API_ROLE), psycopg.sql.Literal(password)
            )
        )
