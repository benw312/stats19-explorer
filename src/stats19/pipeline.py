"""End-to-end orchestration: discover -> download -> raw -> build -> validate -> swap."""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import httpx
import psycopg

from stats19 import marts, transform
from stats19.columns import TABLES
from stats19.download import DownloadedFile, download_file
from stats19.guide import parse_guide
from stats19.load import RawLoad, load_raw
from stats19.reference.derived import rebuild
from stats19.sources import Release, fetch_release
from stats19.validate import (
    DEFAULT_THRESHOLDS,
    CheckResult,
    Thresholds,
    blocking_failures,
    run_checks,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceFiles:
    tables: dict[str, DownloadedFile]
    guide: DownloadedFile
    source_updated_at: str | None


@dataclass(frozen=True)
class LastSuccess:
    source_updated_at: str | None
    sha256: dict[str, str]
    core_counts: dict[str, int]


class ValidationFailed(RuntimeError):
    def __init__(self, failures: list[CheckResult]):
        names = ", ".join(f"{f.check_name}[{f.table_name}]" for f in failures)
        super().__init__(f"validation failed: {names}")
        self.failures = failures


# ------------------------------------------------------------------ run bookkeeping


def last_success(conn: psycopg.Connection) -> LastSuccess | None:
    row = conn.execute(
        """SELECT run_id, source_updated_at FROM etl.run
           WHERE status = 'success' ORDER BY run_id DESC LIMIT 1"""
    ).fetchone()
    if row is None:
        conn.commit()
        return None
    run_id, updated = row
    shas = dict(
        conn.execute(
            "SELECT table_name, sha256 FROM etl.source_file WHERE run_id = %s", (run_id,)
        ).fetchall()
    )
    counts = {
        t: int(n)
        for t, n in conn.execute(
            """SELECT table_name, observed FROM etl.run_check
               WHERE run_id = %s AND check_name = 'core_row_count'""",
            (run_id,),
        ).fetchall()
    }
    conn.commit()
    return LastSuccess(updated, shas, counts)


def last_seen_release(conn: psycopg.Connection) -> str | None:
    """public_updated_at of the newest release already handled (loaded or found unchanged)."""
    row = conn.execute(
        """SELECT source_updated_at FROM etl.run
           WHERE status IN ('success', 'skipped') ORDER BY run_id DESC LIMIT 1"""
    ).fetchone()
    conn.commit()
    return row[0] if row else None


def start_run(conn: psycopg.Connection, source_updated_at: str | None) -> int:
    with conn.transaction():
        return conn.execute(
            "INSERT INTO etl.run (source_updated_at) VALUES (%s) RETURNING run_id",
            (source_updated_at,),
        ).fetchone()[0]


def finish_run(conn: psycopg.Connection, run_id: int, status: str, message: str | None) -> None:
    conn.rollback()  # discard anything left over from a failed statement
    with conn.transaction():
        conn.execute(
            "UPDATE etl.run SET status = %s, message = %s, finished_at = now() WHERE run_id = %s",
            (status, message, run_id),
        )


def _record_files(conn, run_id: int, files: SourceFiles, loads: dict[str, RawLoad]) -> None:
    with conn.transaction():
        for name, f in [*files.tables.items(), ("guide", files.guide)]:
            load = loads.get(name)
            conn.execute(
                """INSERT INTO etl.source_file (run_id, table_name, url, sha256, size_bytes,
                       raw_row_count, header_missing, header_unexpected)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    run_id,
                    name,
                    f.url,
                    f.sha256,
                    f.size_bytes,
                    load.row_count if load else None,
                    load.header.missing if load else [],
                    load.header.unexpected if load else [],
                ),
            )


def _record_checks(conn, run_id: int, results: list[CheckResult]) -> None:
    with conn.transaction():
        for r in results:
            conn.execute(
                """INSERT INTO etl.run_check (run_id, check_name, table_name, severity, passed,
                       observed, threshold, detail)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    run_id,
                    r.check_name,
                    r.table_name,
                    r.severity,
                    r.passed,
                    r.observed,
                    r.threshold,
                    r.detail,
                ),
            )


# ------------------------------------------------------------------ processing


def process(
    conn: psycopg.Connection,
    files: SourceFiles,
    previous: LastSuccess | None,
    keep_previous: bool = False,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> int:
    """Load the given files into core. Returns run_id; raises on failure (run marked failed)."""
    run_id = start_run(conn, files.source_updated_at)
    loads: dict[str, RawLoad] = {}
    try:
        transform.reset_build(conn)
        transform.load_lookups(conn, parse_guide(files.guide.path))

        typed_counts = {}
        for name, spec in TABLES.items():
            loads[name] = load_raw(conn, spec, files.tables[name].path)
            typed_counts[name] = transform.build_typed(conn, spec, set(loads[name].columns))
        _record_files(conn, run_id, files, loads)

        log.info("building keyed core tables (this is the slow step)")
        transform.build_core(conn)
        log.info("building analysis marts")
        marts.build_marts(conn)

        results = run_checks(
            conn,
            raw_columns={n: set(load.columns) for n, load in loads.items()},
            raw_rows={n: load.row_count for n, load in loads.items()},
            typed_counts=typed_counts,
            previous_counts=previous.core_counts if previous else {},
            thresholds=thresholds,
        )
        _record_checks(conn, run_id, results)
        failures = blocking_failures(results)
        if failures:
            raise ValidationFailed(failures)

        transform.swap_in_build(conn, keep_previous=keep_previous)
        with conn.transaction():
            for name in TABLES:
                conn.execute(f"DROP TABLE IF EXISTS raw.{name}")
    except Exception as exc:
        log.exception("run %s failed", run_id)
        finish_run(conn, run_id, "failed", str(exc)[:2000])
        raise
    finish_run(conn, run_id, "success", None)
    log.info("run %s succeeded", run_id)
    _refresh_collision_matches(conn)
    return run_id


def _refresh_collision_matches(conn: psycopg.Connection) -> None:
    """Re-match the new STATS19 data to junctions and road links (PLAN-008 T3), refit the
    safety models and redo the authorities (recording gaps follow the collisions). The load
    itself has succeeded, so a failure here is logged rather than failing the run; the
    builds stay pending and the next check retries them (FU-051)."""
    try:
        rebuild(conn, "junction_collisions", "collision_links", "context", "safety", "authorities")
    except psycopg.Error:
        conn.rollback()
        log.exception(
            "collisions not re-matched to the network; the next check retries "
            "(or run `stats19 rebuild-derived` now)"
        )


# ------------------------------------------------------------------ acquisition


def _release_dir(data_dir: Path, release: Release) -> Path:
    stamp = re.sub(r"[^0-9A-Za-z]+", "-", release.public_updated_at).strip("-")
    return data_dir / "releases" / stamp


def prune_releases(data_dir: Path, keep: int) -> None:
    root = data_dir / "releases"
    if not root.exists():
        return
    dirs = sorted((d for d in root.iterdir() if d.is_dir()), key=lambda d: d.name)
    for old in dirs[:-keep]:
        log.info("removing old release download %s", old)
        shutil.rmtree(old)


def download_release(client: httpx.Client, release: Release, data_dir: Path) -> SourceFiles:
    target = _release_dir(data_dir, release)
    tables = {name: download_file(client, url, target) for name, url in release.csv_urls.items()}
    guide = download_file(client, release.guide_url, target)
    return SourceFiles(tables=tables, guide=guide, source_updated_at=release.public_updated_at)


def run_from_dft(
    conn: psycopg.Connection,
    client: httpx.Client,
    data_dir: Path,
    force: bool = False,
    keep_previous: bool = False,
    keep_releases: int = 2,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> str:
    """Check DfT for a new release and load it. Returns 'skipped' or 'success'."""
    release = fetch_release(client)
    previous = last_success(conn)
    if not force and last_seen_release(conn) == release.public_updated_at:
        log.info("no new release (public_updated_at=%s)", release.public_updated_at)
        return "skipped"

    files = download_release(client, release, data_dir)
    if not force and previous:
        current = {n: f.sha256 for n, f in files.tables.items()}
        if all(previous.sha256.get(n) == sha for n, sha in current.items()):
            log.info("page updated but CSVs unchanged; recording skip")
            run_id = start_run(conn, release.public_updated_at)
            finish_run(conn, run_id, "skipped", "source files unchanged")
            return "skipped"

    process(conn, files, previous, keep_previous=keep_previous, thresholds=thresholds)
    prune_releases(data_dir, keep_releases)
    return "success"
