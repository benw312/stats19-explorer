import csv
import os
from pathlib import Path

import psycopg
import pytest
from openpyxl import Workbook

from stats19.columns import TABLES, Kind
from stats19.download import describe_local_file
from stats19.pipeline import SourceFiles

_DEFAULTS = {
    Kind.KEY_TEXT: "",
    Kind.KEY_INT: "1",
    Kind.TEXT: "",
    Kind.CODE: "1",
    Kind.COUNT: "1",
    Kind.MEASURE: "-1",
    Kind.FLOAT: "",
    Kind.DATE: "01/01/2024",
    Kind.TIME: "12:00",
}


def write_table_csv(path: Path, table: str, rows: list[dict]) -> Path:
    spec = TABLES[table]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(spec.names)
        for row in rows:
            writer.writerow([row.get(c.name, _DEFAULTS[c.kind]) for c in spec.columns])
    return path


def write_guide(path: Path) -> Path:
    """A guide labelling code 1 and -1 for every CODE column."""
    wb = Workbook()
    ws = wb.active
    ws.title = "2024_code_list"
    ws.append(["table", "field name", "code/format", "label", "note"])
    for table, spec in TABLES.items():
        for c in spec.columns:
            if c.kind is Kind.CODE:
                ws.append([table, c.name, 1, "One", None])
                ws.append([table, c.name, -1, "Data missing or out of range", None])
                ws.append([table, c.name, 2, "Two", None])
    conv = wb.create_sheet("2011_to_2024_conversion")
    conv.append(["table", "a", "b", "c", "d", "e", "f"])
    conv.append(["collision", "junction_detail_historic", 3, "T", "junction_detail", 13, "T"])
    wb.save(path)
    return path


@pytest.fixture(autouse=True)
def _clear_api_caches():
    """In-process response caches must not leak between tests (each builds its own data)."""
    from stats19.api.compare import clear_base_cache
    from stats19.api.hotspots import CACHE
    from stats19.api.meta import clear_meta_cache
    from stats19.api.rates import clear_count_cache
    from stats19.api.tiles import TILE_CACHE

    def clear() -> None:
        CACHE.clear()
        TILE_CACHE.clear()
        clear_base_cache()
        clear_count_cache()
        clear_meta_cache()

    clear()
    yield
    clear()


@pytest.fixture
def make_files(tmp_path):
    def _make(collisions, vehicles, casualties) -> SourceFiles:
        paths = {
            "collision": write_table_csv(tmp_path / "collision.csv", "collision", collisions),
            "vehicle": write_table_csv(tmp_path / "vehicle.csv", "vehicle", vehicles),
            "casualty": write_table_csv(tmp_path / "casualty.csv", "casualty", casualties),
        }
        return SourceFiles(
            tables={n: describe_local_file(p) for n, p in paths.items()},
            guide=describe_local_file(write_guide(tmp_path / "guide.xlsx")),
            source_updated_at="test",
        )

    return _make


@pytest.fixture
def db_conn():
    url = os.environ.get("STATS19_TEST_DATABASE_URL")
    if not url:
        pytest.skip("STATS19_TEST_DATABASE_URL not set")
    with psycopg.connect(url, autocommit=True) as admin:
        for schema in (
            "core",
            "core_previous",
            "build",
            "raw",
            "etl",
            "mart",
            "mart_previous",
            "build_mart",
            "geo",
            "app",
        ):
            admin.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    with psycopg.connect(url) as conn:
        yield conn


@pytest.fixture
def api(db_conn, make_files, tmp_path):
    """TestClient over a database loaded with the standard fixture data + reference data."""
    import httpx
    from fastapi.testclient import TestClient

    from stats19 import db
    from stats19.api.app import create_app
    from stats19.pipeline import last_success, process
    from stats19.reference.refresh import refresh_reference

    from .test_pipeline_integration import GOOD_CASUALTIES, GOOD_COLLISIONS, GOOD_VEHICLES, LENIENT
    from .test_reference_load import _transport

    db.migrate(db_conn)
    process(
        db_conn,
        make_files(GOOD_COLLISIONS, GOOD_VEHICLES, GOOD_CASUALTIES),
        last_success(db_conn),
        thresholds=LENIENT,
    )
    with httpx.Client(transport=_transport([])) as client:
        refresh_reference(db_conn, client, tmp_path)
    with TestClient(create_app(os.environ["STATS19_TEST_DATABASE_URL"])) as c:
        yield c
