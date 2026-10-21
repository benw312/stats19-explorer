"""Every API response carries a short reference that matches its log line (FU-050)."""

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from stats19.api.access import EDGE_HEADER, install_access_check
from stats19.api.envelope import ApiError, NotFound, install_error_handlers
from stats19.api.request_log import REF_HEADER, install_request_log


def make_app() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)
    install_access_check(app, None)
    install_request_log(app)

    @app.get("/api/ok")
    def fine() -> dict:
        return {"success": True}

    @app.get("/api/health")
    def health() -> dict:
        return {"success": True}

    @app.get("/api/boom")
    def boom() -> dict:
        raise RuntimeError("database fell over")

    @app.get("/api/missing")
    def missing() -> dict:
        raise NotFound("Collision not found")

    @app.get("/api/busy")
    def busy() -> dict:
        raise ApiError(503, "busy", "Try again")

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client():
    return make_app()


def test_a_crash_returns_an_envelope_with_the_ref_and_logs_the_traceback(client, caplog):
    with caplog.at_level(logging.INFO, logger="stats19.api"):
        r = client.get("/api/boom")

    assert r.status_code == 500
    error = r.json()["error"]
    assert error["code"] == "internal_error"
    assert "database fell over" not in r.text  # details stay in the log
    assert error["ref"] == r.headers[REF_HEADER]
    crash = next(rec for rec in caplog.records if rec.exc_info)
    assert f"ref={error['ref']}" in crash.getMessage()
    assert "database fell over" in caplog.text


@pytest.mark.parametrize(("path", "status"), [("/api/missing", 404), ("/api/busy", 503)])
def test_handled_errors_carry_the_ref_too(client, path, status):
    r = client.get(path)

    assert r.status_code == status
    assert r.json()["error"]["ref"] == r.headers[REF_HEADER]


def test_access_refusals_carry_the_ref(client):
    r = client.get("/api/ok", headers={EDGE_HEADER: "tunnel"})

    assert r.status_code == 401
    assert r.json()["error"]["ref"] == r.headers[REF_HEADER]


def test_each_request_is_logged_once_with_status_and_ref(client, caplog):
    with caplog.at_level(logging.INFO, logger="stats19.api"):
        r = client.get("/api/ok?f=" + "x" * 1000)

    lines = [rec.getMessage() for rec in caplog.records if rec.name == "stats19.api"]
    assert len(lines) == 1
    assert "200" in lines[0] and f"ref={r.headers[REF_HEADER]}" in lines[0]
    assert len(lines[0]) < 500  # long filters are cut short


def test_healthy_health_checks_are_not_logged(client, caplog):
    with caplog.at_level(logging.INFO, logger="stats19.api"):
        client.get("/api/health")

    assert not [rec for rec in caplog.records if rec.name == "stats19.api"]
