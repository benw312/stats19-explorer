"""Command-line entry point: ``stats19 <command>``."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import httpx

from stats19 import db, pipeline
from stats19.config import load_settings
from stats19.download import describe_local_file
from stats19.reference import derived
from stats19.reference import refresh as reference

log = logging.getLogger("stats19")


def _client(timeout_s: float) -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(timeout_s, connect=30.0),
        follow_redirects=True,
        transport=httpx.HTTPTransport(retries=3),
        headers={"User-Agent": "stats19-pipeline (+https://github.com/benw312/stats19)"},
    )


def cmd_migrate(args, settings) -> int:
    with db.connect(settings.database_url) as conn:
        applied = db.migrate(conn, settings.api_db_password)
    log.info("migrations applied: %s", applied or "none")
    return 0


def cmd_run(args, settings) -> int:
    with db.connect(settings.database_url) as conn, _client(settings.http_timeout_s) as client:
        db.migrate(conn, settings.api_db_password)
        pipeline.run_from_dft(
            conn,
            client,
            settings.data_dir,
            force=args.force,
            keep_previous=args.keep_previous,
            keep_releases=settings.keep_releases,
        )
    return 0


def cmd_load_local(args, settings) -> int:
    files = pipeline.SourceFiles(
        tables={
            "collision": describe_local_file(args.collision),
            "vehicle": describe_local_file(args.vehicle),
            "casualty": describe_local_file(args.casualty),
        },
        guide=describe_local_file(args.guide),
        source_updated_at=None,
    )
    with db.connect(settings.database_url) as conn:
        db.migrate(conn, settings.api_db_password)
        pipeline.process(conn, files, pipeline.last_success(conn), keep_previous=args.keep_previous)
    return 0


def cmd_refresh_reference(args, settings) -> int:
    with db.connect(settings.database_url) as conn, _client(settings.http_timeout_s) as client:
        db.migrate(conn, settings.api_db_password)
        if args.if_stale:
            done = reference.refresh_if_stale(conn, client, settings.data_dir, args.max_age_days)
        else:
            done = reference.refresh_reference(conn, client, settings.data_dir, args.dataset)
    log.info("reference datasets refreshed: %s", done or "none (all fresh)")
    return 0


def cmd_rebuild_derived(args, settings) -> int:
    with db.connect(settings.database_url) as conn:
        db.migrate(conn, settings.api_db_password)
        if args.step:
            derived.rebuild(conn, *args.step)
            done = derived.plan(set(args.step))
        else:
            done = derived.run_pending(conn)
    log.info("derived tables rebuilt: %s", done or "none (nothing pending)")
    return 0


def cmd_serve(args, settings) -> int:
    import uvicorn

    from stats19.api.access import AccessVerifier
    from stats19.api.app import create_app

    access = AccessVerifier.from_settings(settings.access_team_domain, settings.access_aud)
    uvicorn.run(
        create_app(settings.database_url, settings.report_base_url, access),
        host=args.host,
        port=args.port,
        access_log=False,  # stats19.api.request_log logs each request, with its ref
    )
    return 0


def cmd_watch(args, settings) -> int:
    """Long-running scheduler: check for a new release every N hours."""
    interval = args.interval_hours * 3600
    while True:
        try:
            cmd_run(argparse.Namespace(force=False, keep_previous=False), settings)
        except Exception:
            log.exception("scheduled run failed; will retry next interval")
        try:
            cmd_refresh_reference(
                argparse.Namespace(if_stale=True, max_age_days=args.reference_max_age_days),
                settings,
            )
        except Exception:
            log.exception("reference refresh failed; will retry next interval")
        log.info("next check in %.1f hours", args.interval_hours)
        time.sleep(interval)


def cmd_status(args, settings) -> int:
    with db.connect(settings.database_url) as conn:
        runs = conn.execute(
            """SELECT run_id, status, started_at, finished_at, source_updated_at, message
               FROM etl.run ORDER BY run_id DESC LIMIT %s""",
            (args.limit,),
        ).fetchall()
        for run_id, status, started, finished, updated, message in runs:
            ended = f"{finished:%H:%M}" if finished else "…"
            print(
                f"run {run_id:>4} {status:<8} {started:%Y-%m-%d %H:%M} -> {ended}"
                f"  source={updated}  {message or ''}"
            )
        if runs:
            for r in conn.execute(
                """SELECT check_name, table_name, severity, passed, observed, detail
                   FROM etl.run_check WHERE run_id = %s ORDER BY passed, severity""",
                (runs[0][0],),
            ):
                print("   ", "ok  " if r[3] else "FAIL", *r[:3], r[4], r[5] or "")
        pending = conn.execute(
            "SELECT step, requested_at FROM etl.derived_pending ORDER BY requested_at"
            if conn.execute("SELECT to_regclass('etl.derived_pending')").fetchone()[0]
            else "SELECT NULL, NULL WHERE false"
        ).fetchall()
        for step, requested in pending:
            print(f"derived build pending: {step} (asked for {requested:%Y-%m-%d %H:%M})")
    return 0


def cmd_feedback(args, settings) -> int:
    """List feedback from the app (FU-055), or mark one item seen or done."""
    from stats19 import feedback

    with db.connect(settings.database_url) as conn:
        if args.done is not None or args.seen is not None:
            item, status = (args.done, "done") if args.done is not None else (args.seen, "seen")
            if not feedback.set_status(conn, item, status, args.note):
                print(f"no feedback item {item}")
                return 1
            print(f"feedback {item}: {status}")
            return 0
        rows = feedback.list_items(conn, include_done=args.all, limit=args.limit)
        print(feedback.format_items(rows) if rows else "no feedback to show")
    return 0


def cmd_safety_check(args, settings) -> int:
    from stats19.reference.safety_check import format_results, run_check

    with db.connect(settings.database_url) as conn:
        print(format_results(*run_check(conn)))
    return 0


def cmd_context_check(args, settings) -> int:
    from stats19.reference.context_check import format_results, run_check

    with db.connect(settings.database_url) as conn:
        since = args.since
        if since is None:
            latest = conn.execute("SELECT max(collision_year) FROM core.collision").fetchone()[0]
            since = latest - 19
        print(format_results(since, run_check(conn, since)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="stats19", description=__doc__)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate", help="apply database migrations").set_defaults(func=cmd_migrate)

    run = sub.add_parser("run", help="fetch the latest DfT release and load it if new")
    run.add_argument("--force", action="store_true", help="reload even if unchanged")
    run.add_argument(
        "--keep-previous",
        action="store_true",
        help="keep the replaced data as schema core_previous",
    )
    run.set_defaults(func=cmd_run)

    local = sub.add_parser("load-local", help="load CSVs + guide already on disk")
    for name in ("collision", "vehicle", "casualty", "guide"):
        local.add_argument(f"--{name}", type=Path, required=True)
    local.add_argument("--keep-previous", action="store_true")
    local.set_defaults(func=cmd_load_local)

    watch = sub.add_parser("watch", help="run forever, checking for releases periodically")
    watch.add_argument("--interval-hours", type=float, default=24.0)
    watch.add_argument("--reference-max-age-days", type=int, default=90)
    watch.set_defaults(func=cmd_watch)

    ref = sub.add_parser("refresh-reference", help="download/reload postcodes, places, boundaries")
    ref.add_argument("--dataset", action="append", choices=list(reference.DATASETS))
    ref.add_argument("--if-stale", action="store_true", help="only datasets older than max age")
    ref.add_argument("--max-age-days", type=int, default=90)
    ref.set_defaults(func=cmd_refresh_reference)

    redo = sub.add_parser(
        "rebuild-derived",
        help="run derived builds left pending by a failure (or the --step ones named)",
    )
    redo.add_argument("--step", action="append", choices=list(derived.ORDER))
    redo.set_defaults(func=cmd_rebuild_derived)

    serve = sub.add_parser("serve", help="run the HTTP API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=cmd_serve)

    status = sub.add_parser("status", help="show recent runs and the latest checks")
    status.add_argument("--limit", type=int, default=5)
    status.set_defaults(func=cmd_status)

    fb = sub.add_parser("feedback", help="list feedback sent from the app; mark it seen or done")
    fb.add_argument("--all", action="store_true", help="include items marked done")
    fb.add_argument("--limit", type=int, default=50)
    fb.add_argument("--seen", type=int, metavar="ID", help="mark one item seen")
    fb.add_argument("--done", type=int, metavar="ID", help="mark one item done")
    fb.add_argument("--note", help="a note to keep with --seen or --done")
    fb.set_defaults(func=cmd_feedback)

    check = sub.add_parser(
        "safety-check",
        help="out-of-sample check of the safety ranking: earlier five years vs the latest",
    )
    check.set_defaults(func=cmd_safety_check)

    sun = sub.add_parser(
        "context-check",
        help="check the sun bands: low sun ahead against behind, in fine weather and in rain",
    )
    sun.add_argument("--since", type=int, help="first year (default: the last 20 years)")
    sun.set_defaults(func=cmd_context_check)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    try:
        return args.func(args, load_settings())
    except Exception as exc:
        log.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
