"""Runtime settings from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    pass


# Where the PDF renderer loads the web app's /print pages from. In Docker this is the
# Caddy service (http://web); on a dev machine, the Vite dev server or Caddy on :8080.
DEFAULT_REPORT_BASE_URL = "http://localhost:8080"


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_dir: Path
    keep_releases: int = 2
    http_timeout_s: float = 600.0
    report_base_url: str = DEFAULT_REPORT_BASE_URL
    # Cloudflare Access (PLAN-006): both set, or tunnel requests are refused
    access_team_domain: str | None = None
    access_aud: str | None = None
    # the API's read-only database role (PLAN-006 C4): set to let it log in
    api_db_password: str | None = None


def load_settings(env: dict[str, str] | None = None) -> Settings:
    env = dict(os.environ if env is None else env)
    url = env.get("STATS19_DATABASE_URL")
    if not url:
        raise ConfigError("STATS19_DATABASE_URL is not set (see .env.example)")
    try:
        keep = int(env.get("STATS19_KEEP_RELEASES", "2"))
    except ValueError as exc:
        raise ConfigError("STATS19_KEEP_RELEASES must be an integer") from exc
    if keep < 1:
        raise ConfigError("STATS19_KEEP_RELEASES must be at least 1")
    return Settings(
        database_url=url,
        data_dir=Path(env.get("STATS19_DATA_DIR", "data")),
        keep_releases=keep,
        report_base_url=env.get("STATS19_REPORT_BASE_URL", DEFAULT_REPORT_BASE_URL),
        access_team_domain=env.get("STATS19_ACCESS_TEAM_DOMAIN") or None,
        access_aud=env.get("STATS19_ACCESS_AUD") or None,
        api_db_password=env.get("STATS19_API_DB_PASSWORD") or None,
    )
