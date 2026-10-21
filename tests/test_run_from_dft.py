"""run_from_dft: release detection, skip logic and download pruning."""

import httpx
import pytest

from stats19 import db
from stats19.cli import build_parser
from stats19.pipeline import prune_releases, run_from_dft
from stats19.sources import CONTENT_API_URL

from .test_pipeline_integration import GOOD_CASUALTIES, GOOD_COLLISIONS, GOOD_VEHICLES, LENIENT

FILE_BASE = "https://data.dft.gov.uk/road-accidents-safety-data/dft-road-casualty-statistics"
GUIDE_URL = "https://assets.publishing.service.gov.uk/media/x/open-dataset-data-guide-2025.xlsx"


def _mock_dft(files, updated_at: str):
    """Serve a content API response plus the given SourceFiles over a MockTransport."""
    by_url = {
        f"{FILE_BASE}-{n}-1979-latest-published-year.csv": f.path for n, f in files.tables.items()
    }
    by_url[GUIDE_URL] = files.guide.path
    body = "".join(f'<a href="{u}">x</a>' for u in by_url)
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requested.append(url)
        if url == CONTENT_API_URL:
            return httpx.Response(
                200, json={"public_updated_at": updated_at, "details": {"body": body}}
            )
        return httpx.Response(200, content=by_url[url].read_bytes())

    return httpx.Client(transport=httpx.MockTransport(handler)), requested


@pytest.fixture
def good_files(make_files):
    return make_files(GOOD_COLLISIONS, GOOD_VEHICLES, GOOD_CASUALTIES)


@pytest.mark.integration
def test_new_release_is_downloaded_and_loaded(db_conn, good_files, tmp_path):
    db.migrate(db_conn)
    client, _ = _mock_dft(good_files, "2026-07-30T09:30:07+01:00")

    status = run_from_dft(db_conn, client, tmp_path / "data", thresholds=LENIENT)

    assert status == "success"
    assert db_conn.execute("SELECT count(*) FROM core.collision").fetchone() == (2,)
    release_dir = tmp_path / "data/releases/2026-07-30T09-30-07-01-00"
    assert sorted(p.name for p in release_dir.iterdir()) == [
        "dft-road-casualty-statistics-casualty-1979-latest-published-year.csv",
        "dft-road-casualty-statistics-collision-1979-latest-published-year.csv",
        "dft-road-casualty-statistics-vehicle-1979-latest-published-year.csv",
        "open-dataset-data-guide-2025.xlsx",
    ]


@pytest.mark.integration
def test_unchanged_page_skips_without_downloading(db_conn, good_files, tmp_path):
    db.migrate(db_conn)
    client, _ = _mock_dft(good_files, "T1")
    run_from_dft(db_conn, client, tmp_path, thresholds=LENIENT)

    client, requested = _mock_dft(good_files, "T1")
    status = run_from_dft(db_conn, client, tmp_path, thresholds=LENIENT)

    assert status == "skipped"
    assert requested == [CONTENT_API_URL]


@pytest.mark.integration
def test_updated_page_with_identical_files_records_skip(db_conn, good_files, tmp_path):
    db.migrate(db_conn)
    client, _ = _mock_dft(good_files, "T1")
    run_from_dft(db_conn, client, tmp_path, thresholds=LENIENT)

    client, _ = _mock_dft(good_files, "T2")
    status = run_from_dft(db_conn, client, tmp_path, thresholds=LENIENT)

    assert status == "skipped"
    assert db_conn.execute(
        "SELECT status, message FROM etl.run ORDER BY run_id DESC LIMIT 1"
    ).fetchone() == ("skipped", "source files unchanged")

    # the next check must not download the unchanged release again
    client, requested = _mock_dft(good_files, "T2")
    assert run_from_dft(db_conn, client, tmp_path, thresholds=LENIENT) == "skipped"
    assert requested == [CONTENT_API_URL]


@pytest.mark.integration
def test_force_reloads_unchanged_release(db_conn, good_files, tmp_path):
    db.migrate(db_conn)
    client, _ = _mock_dft(good_files, "T1")
    run_from_dft(db_conn, client, tmp_path, thresholds=LENIENT)

    client, _ = _mock_dft(good_files, "T1")
    status = run_from_dft(db_conn, client, tmp_path, force=True, thresholds=LENIENT)

    assert status == "success"
    assert db_conn.execute("SELECT count(*) FROM etl.run WHERE status = 'success'").fetchone() == (
        2,
    )


def test_prune_releases_keeps_newest(tmp_path):
    for name in ("2024-07-01", "2025-07-01", "2026-07-30"):
        (tmp_path / "releases" / name).mkdir(parents=True)

    prune_releases(tmp_path, keep=2)

    assert sorted(p.name for p in (tmp_path / "releases").iterdir()) == ["2025-07-01", "2026-07-30"]


def test_prune_releases_tolerates_missing_dir(tmp_path):
    prune_releases(tmp_path, keep=1)


@pytest.mark.parametrize(
    "argv",
    [
        ["migrate"],
        ["run", "--force"],
        ["watch", "--interval-hours", "6"],
        ["status"],
        ["serve", "--port", "9000"],
        ["refresh-reference", "--if-stale"],
        ["refresh-reference", "--dataset", "postcode", "--dataset", "boundary"],
        ["load-local", "--collision", "a", "--vehicle", "b", "--casualty", "c", "--guide", "d"],
    ],
)
def test_cli_parses_commands(argv):
    args = build_parser().parse_args(argv)

    assert callable(args.func)
