"""`stats19 serve` (the API container's command) must pass the Access settings on."""

import uvicorn

from stats19 import cli
from stats19.config import load_settings

TEAM = "team.cloudflareaccess.com"
AUD = "aud-tag-123"


def served_app(monkeypatch, env: dict):
    captured = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **_: captured.setdefault("app", app))
    args = cli.build_parser().parse_args(["serve"])
    cli.cmd_serve(args, load_settings({"STATS19_DATABASE_URL": "postgresql://x/y"} | env))
    return captured["app"]


def test_serve_checks_access_tokens_when_configured(monkeypatch):
    app = served_app(monkeypatch, {"STATS19_ACCESS_TEAM_DOMAIN": TEAM, "STATS19_ACCESS_AUD": AUD})

    assert app.state.access is not None
    assert app.state.access.issuer == f"https://{TEAM}"
    assert app.state.access.audience == AUD


def test_serve_without_access_settings_refuses_the_tunnel(monkeypatch):
    assert served_app(monkeypatch, {}).state.access is None
