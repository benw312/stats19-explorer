"""The API's read-only database role (PLAN-006 C4)."""

import os
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from stats19 import db

pytestmark = pytest.mark.integration

PASSWORD = "test-api-role-password"


def _as_api(url: str) -> str:
    parts = urlsplit(url)
    host = parts.netloc.rsplit("@", 1)[-1]
    return urlunsplit(parts._replace(netloc=f"{db.API_ROLE}:{PASSWORD}@{host}"))


def test_api_role_reads_but_cannot_write_and_sees_rebuilt_tables(db_conn):
    db.migrate(db_conn, PASSWORD)
    db_conn.execute("CREATE SCHEMA IF NOT EXISTS geo")
    db_conn.execute("CREATE TABLE geo.role_probe AS SELECT 1 AS x")
    db_conn.commit()

    with psycopg.connect(_as_api(os.environ["STATS19_TEST_DATABASE_URL"])) as api:
        assert api.execute("SELECT x FROM geo.role_probe").fetchone() == (1,)
        for statement in (
            "INSERT INTO geo.role_probe VALUES (2)",
            "CREATE TABLE geo.role_probe_2 (x int)",
            "DROP TABLE geo.role_probe",
        ):
            with pytest.raises(psycopg.Error):
                api.execute(statement)
            api.rollback()

    # the pipeline rebuilds a table (drop + create): default privileges keep it readable
    db_conn.execute("DROP TABLE geo.role_probe")
    db_conn.execute("CREATE TABLE geo.role_probe AS SELECT 3 AS x")
    db_conn.commit()
    with psycopg.connect(_as_api(os.environ["STATS19_TEST_DATABASE_URL"])) as api:
        assert api.execute("SELECT x FROM geo.role_probe").fetchone() == (3,)


SQUARE_BNG = (
    "ST_GeomFromText('POLYGON((375000 165000,375100 165000,375100 165100,375000 165000))', 27700)"
)


def test_api_role_writes_only_schemes_and_only_when_asked(db_conn):
    """V5 (PLAN-011 §5): the role may add and edit schemes in a READ WRITE transaction,
    and nothing else, ever."""
    db.migrate(db_conn, PASSWORD)
    db_conn.execute("CREATE SCHEMA IF NOT EXISTS geo")
    db_conn.execute("CREATE TABLE geo.role_probe AS SELECT 1 AS x")
    db_conn.commit()
    insert = (
        "INSERT INTO app.scheme (org_id, name, measure, site_type, geom_bng, created_by,"
        " updated_by) VALUES ('00000000-0000-0000-0000-000000000001', %s, 'signals',"
        f" 'junction', {SQUARE_BNG}, 'test', 'test')"
    )

    with psycopg.connect(_as_api(os.environ["STATS19_TEST_DATABASE_URL"])) as api:
        # read-only unless the transaction asks
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            api.execute(insert, ("Read-only",))
        api.rollback()

        with api.transaction():
            api.execute("SET TRANSACTION READ WRITE")
            api.execute(insert, ("Allowed",))
            api.execute("UPDATE app.scheme SET name = 'Renamed', deleted_at = now()")

        for statement in (
            "INSERT INTO geo.role_probe VALUES (2)",
            "UPDATE app.scheme SET org_id = gen_random_uuid()",
            "UPDATE app.scheme SET created_by = 'someone else'",
            "DELETE FROM app.scheme",
            "INSERT INTO app.org (id, name) VALUES (gen_random_uuid(), 'Other')",
            "DROP TABLE app.scheme",
            "CREATE TABLE app.extra (x int)",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), api.transaction():
                api.execute("SET TRANSACTION READ WRITE")
                api.execute(statement)

    assert db_conn.execute("SELECT name FROM app.scheme").fetchall() == [("Renamed",)]


def test_the_schemes_api_works_as_the_api_role(db_conn, monkeypatch):
    """End to end: the write path under the real read-only role."""
    from fastapi.testclient import TestClient

    from stats19.api import writes
    from stats19.api.app import create_app
    from stats19.api.limits import RateLimit

    from .test_schemes import SAME_SITE, scheme

    monkeypatch.setattr(writes, "LIMIT", RateLimit(100, 60))
    db.migrate(db_conn, PASSWORD)
    with TestClient(create_app(_as_api(os.environ["STATS19_TEST_DATABASE_URL"]))) as client:
        created = client.post("/api/schemes", json=scheme(), headers=SAME_SITE)
        assert created.status_code == 201, created.text
        sid = created.json()["data"]["id"]
        edit = scheme(name="Edited") | {"version": 1}
        assert client.put(f"/api/schemes/{sid}", json=edit, headers=SAME_SITE).status_code == 200
        assert client.delete(f"/api/schemes/{sid}", headers=SAME_SITE).status_code == 200
        assert client.get("/api/schemes").json()["data"] == []
