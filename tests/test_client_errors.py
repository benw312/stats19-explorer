"""POST /api/client-errors: browser crashes land in the API log (FU-050)."""

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from stats19.api import client_errors
from stats19.api.client_errors import RateLimit
from stats19.api.envelope import install_error_handlers


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(client_errors, "LIMIT", RateLimit(3, 60))
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(client_errors.router, prefix="/api")
    return TestClient(app)


def report(**overrides) -> dict:
    return {
        "ref": "a1b2c3",
        "kind": "render",
        "message": "Cannot read properties of undefined (reading 'rate')",
        "stack": "TypeError: ...\n    at RatesTab (RatesTab.tsx:40)\n    at App",
        "url": "/?view=area",
        "version": "18201cc",
    } | overrides


def test_a_report_is_logged_with_its_ref(client, caplog):
    with caplog.at_level(logging.WARNING, logger="stats19.client"):
        r = client.post("/api/client-errors", json=report())

    assert r.status_code == 200
    assert r.json()["data"] == {"ref": "a1b2c3"}
    assert "ref=a1b2c3" in caplog.text
    assert "version=18201cc" in caplog.text
    assert "at RatesTab (RatesTab.tsx:40)" in caplog.text


def test_reported_text_cannot_forge_log_lines(client, caplog):
    with caplog.at_level(logging.WARNING, logger="stats19.client"):
        client.post(
            "/api/client-errors",
            json=report(message="oops\n2026-10-08 INFO stats19.api: GET /api/fake 200", stack=None),
        )

    assert len(caplog.records) == 1
    assert "\n" not in caplog.records[0].getMessage()


@pytest.mark.parametrize(
    "bad",
    [
        {"ref": "../../etc"},
        {"ref": "A1B2C3"},
        {"kind": "anything"},
        {"message": "x" * 501},
        {"stack": "x" * 4001},
    ],
)
def test_malformed_reports_are_refused(client, bad):
    assert client.post("/api/client-errors", json=report(**bad)).status_code == 422


def test_reports_beyond_the_rate_limit_are_dropped(client, caplog):
    with caplog.at_level(logging.WARNING, logger="stats19.client"):
        codes = [client.post("/api/client-errors", json=report()).status_code for _ in range(5)]

    assert codes == [200, 200, 200, 429, 429]
    assert len(caplog.records) == 3


def test_the_rate_limit_window_moves_on():
    now = [0.0]
    limit = RateLimit(2, 10, clock=lambda: now[0])

    assert [limit.allow(), limit.allow(), limit.allow()] == [True, True, False]
    now[0] = 10.0
    assert limit.allow()
