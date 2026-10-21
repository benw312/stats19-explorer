"""Feedback from the app (FU-055): the API, the API role's rights, and the CLI helpers."""

import os
from datetime import datetime

import psycopg
import pytest
from fastapi.testclient import TestClient

from stats19 import db, feedback
from stats19.api import writes
from stats19.api.app import create_app
from stats19.api.limits import RateLimit

from .test_api_role import PASSWORD, _as_api

SAME_SITE = {"Origin": "http://testserver"}


def item(**overrides) -> dict:
    return {
        "kind": "problem",
        "message": "The junction page didn't load after I picked Bath.",
        "url": "/?view=sites&jn=J1&a=E06000022#map=15/51.38/-2.36",
        "version": "8addba3",
        "user_agent": "Mozilla/5.0 (Macintosh) Safari/605.1.15",
        "viewport": "1440×900 @2x",
        "error_ref": "a1b2c3",
        "contact_ok": True,
    } | overrides


@pytest.fixture
def client(db_conn, monkeypatch):
    monkeypatch.setattr(writes, "LIMIT", RateLimit(1000, 60))
    db.migrate(db_conn)
    with TestClient(create_app(os.environ["STATS19_TEST_DATABASE_URL"])) as c:
        yield c


@pytest.mark.integration
def test_feedback_is_stored_with_its_context_and_ref(client, db_conn):
    r = client.post("/api/feedback", json=item(), headers=SAME_SITE)

    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["ref"] == r.headers["X-Request-Ref"]
    row = db_conn.execute(
        "SELECT kind, message, url, viewport, error_ref, request_ref, created_by, status, org_id"
        " FROM app.feedback WHERE id = %s",
        (data["id"],),
    ).fetchone()
    assert row[:5] == (
        "problem",
        "The junction page didn't load after I picked Bath.",
        "/?view=sites&jn=J1&a=E06000022#map=15/51.38/-2.36",
        "1440×900 @2x",
        "a1b2c3",
    )
    assert row[5] == data["ref"]
    assert (row[6], row[7], str(row[8])) == ("LAN", "new", "00000000-0000-0000-0000-000000000001")


@pytest.mark.integration
@pytest.mark.parametrize(
    "headers, kwargs, status",
    [
        ({}, {"json": item()}, 403),
        ({"Origin": "https://evil.example"}, {"json": item()}, 403),
        (SAME_SITE, {"data": {"message": "x"}}, 415),
    ],
)
def test_feedback_needs_same_site_json(client, db_conn, headers, kwargs, status):
    assert client.post("/api/feedback", headers=headers, **kwargs).status_code == status
    assert db_conn.execute("SELECT count(*) FROM app.feedback").fetchone()[0] == 0


@pytest.mark.integration
@pytest.mark.parametrize(
    "overrides",
    [
        {"message": "   "},
        {"message": "x" * 2001},
        {"kind": "rant"},
        {"error_ref": "not-a-ref"},
        {"viewport": "<script>"},
        {"extra": 1},
    ],
)
def test_bad_feedback_is_refused(client, overrides):
    r = client.post("/api/feedback", json=item(**overrides), headers=SAME_SITE)
    assert r.status_code == 422, r.text


@pytest.mark.integration
def test_the_api_role_may_add_feedback_but_not_triage_it(db_conn):
    db.migrate(db_conn, PASSWORD)
    insert = (
        "INSERT INTO app.feedback (org_id, kind, message, url, created_by)"
        " VALUES ('00000000-0000-0000-0000-000000000001', 'idea', 'More colours', '/', 'LAN')"
    )
    with psycopg.connect(_as_api(os.environ["STATS19_TEST_DATABASE_URL"])) as api:
        with api.transaction():
            api.execute("SET TRANSACTION READ WRITE")
            api.execute(insert)
        for statement in ("UPDATE app.feedback SET status = 'done'", "DELETE FROM app.feedback"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), api.transaction():
                api.execute("SET TRANSACTION READ WRITE")
                api.execute(statement)


@pytest.mark.integration
def test_cli_lists_new_items_and_marks_them(client, db_conn):
    first = client.post("/api/feedback", json=item(), headers=SAME_SITE).json()["data"]["id"]
    client.post(
        "/api/feedback",
        json=item(kind="liked", message="Stick diagrams are great", contact_ok=False),
        headers=SAME_SITE,
    )
    db_conn.commit()

    assert feedback.count_new(db_conn) == 2
    assert feedback.set_status(db_conn, first, "done", "Fixed in #49")
    assert not feedback.set_status(db_conn, 999_999, "seen", None)

    open_items = feedback.list_items(db_conn)
    assert [r[2] for r in open_items] == ["liked"]
    text = feedback.format_items(feedback.list_items(db_conn, include_done=True))
    assert "Liked  [new]" in text and "(no contact)" in text
    assert "[done]" in text and "note: Fixed in #49" in text
    assert "error ref a1b2c3" in text
    assert feedback.count_new(db_conn) == 1


def test_cli_helpers_cope_before_the_migration(db_conn):
    assert feedback.list_items(db_conn) == []
    assert feedback.count_new(db_conn) == 0
    assert not feedback.set_status(db_conn, 1, "done", None)
    with pytest.raises(ValueError):
        feedback.set_status(db_conn, 1, "deleted", None)


def test_format_keeps_a_message_on_its_own_wrapped_lines():
    row = (
        7,
        datetime(2026, 10, 10, 9, 30),
        "question",
        "seen",
        "a@b.org",
        True,
        "/",
        None,
        None,
        None,
        None,
        None,
        "line one\nline two " + "word " * 30,
        None,
    )
    text = feedback.format_items([row])
    assert text.startswith("#7  Question  [seen]  2026-10-10 09:30  a@b.org")
    assert all(len(line) <= 90 for line in text.splitlines())
