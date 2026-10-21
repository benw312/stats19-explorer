"""/api/health and /api/meta: what data is loaded and which fields can be sliced."""

from __future__ import annotations

import threading
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends

from stats19.api import cache, export, summary
from stats19.api.deps import get_conn
from stats19.api.envelope import ok
from stats19.version import version

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]


@router.get("/health")
def health(conn: Conn) -> dict:
    database = conn.execute("SELECT 1 AS ok").fetchone()["ok"] == 1
    return ok({"status": "ok", "database": database, "version": version()})


# Every page load asks for meta, and counting the collisions takes a few hundred ms (FU-052).
# It only changes with a data load or a reference refresh, so it's kept until either happens.
_meta_cache: dict[str, dict] = {}
_meta_lock = threading.Lock()


def _meta_key(conn: psycopg.Connection) -> str:
    refreshed = conn.execute(
        "SELECT max(refreshed_at) AS at FROM geo.reference_refresh"
    ).fetchone()["at"]
    return f"{cache.data_load(conn)}|{refreshed}"


def clear_meta_cache() -> None:
    with _meta_lock:
        _meta_cache.clear()


@router.get("/meta")
def meta(conn: Conn) -> dict:
    key = _meta_key(conn)
    with _meta_lock:
        data = _meta_cache.get(key)
    if data is None:
        data = _meta_data(conn)
        with _meta_lock:
            _meta_cache.clear()  # only the current key is ever useful
            _meta_cache[key] = data
    return ok(data | {"version": version()})


def _meta_data(conn: psycopg.Connection) -> dict:
    coverage = conn.execute(
        """SELECT min(collision_year) AS first_year, max(collision_year) AS last_year,
                  count(*) AS collisions FROM core.collision"""
    ).fetchone()
    last_run = conn.execute(
        """SELECT run_id, status, finished_at, source_updated_at FROM etl.run
           WHERE status = 'success' ORDER BY run_id DESC LIMIT 1"""
    ).fetchone()
    reference = conn.execute(
        "SELECT dataset, refreshed_at, source, row_count FROM geo.reference_refresh ORDER BY 1"
    ).fetchall()
    codes: dict[tuple[str, str], list[dict]] = {}
    for r in conn.execute(
        """SELECT table_name, field_name, code::int AS code, label FROM core.lookup_code
           WHERE code ~ '^-?[0-9]+$' ORDER BY table_name, field_name, code::int"""
    ):
        codes.setdefault((r["table_name"], r["field_name"]), []).append(
            {"code": r["code"], "label": r["label"]}
        )
    fields = conn.execute(
        """SELECT table_name, field_name, kind, sql_type, description, first_year, last_year,
                  is_labelled, harmonisation_note
           FROM mart.field_catalog ORDER BY table_name, field_name"""
    ).fetchall()
    for f in fields:
        f["codes"] = (
            codes.get((f["table_name"], f["field_name"]), []) if f["kind"] == "code" else []
        )
    limits = {
        "summary": summary.MAX_SUMMARY_COLLISIONS,
        "export_csv": export.MAX_EXPORT_COLLISIONS,
        "export_xlsx": export.MAX_XLSX_COLLISIONS,
    }
    return {
        "coverage": coverage,
        "last_run": last_run,
        "reference": reference,
        "fields": fields,
        "limits": limits,
    }
