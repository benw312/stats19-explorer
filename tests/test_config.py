from pathlib import Path

import pytest

from stats19.config import ConfigError, load_settings


def test_load_settings_requires_database_url():
    with pytest.raises(ConfigError, match="STATS19_DATABASE_URL"):
        load_settings({})


def test_load_settings_defaults():
    s = load_settings({"STATS19_DATABASE_URL": "postgresql://x"})

    assert s.database_url == "postgresql://x"
    assert s.data_dir == Path("data")
    assert s.keep_releases == 2
    assert s.report_base_url == "http://localhost:8080"


def test_report_base_url_from_env():
    s = load_settings({"STATS19_DATABASE_URL": "x", "STATS19_REPORT_BASE_URL": "http://web"})

    assert s.report_base_url == "http://web"


@pytest.mark.parametrize("value", ["zero", "0", "-3"])
def test_load_settings_rejects_bad_keep_releases(value):
    with pytest.raises(ConfigError, match="KEEP_RELEASES"):
        load_settings({"STATS19_DATABASE_URL": "x", "STATS19_KEEP_RELEASES": value})


def test_cloudflare_access_settings_are_optional():
    s = load_settings({"STATS19_DATABASE_URL": "postgresql://x"})
    assert s.access_team_domain is None and s.access_aud is None

    s = load_settings(
        {
            "STATS19_DATABASE_URL": "postgresql://x",
            "STATS19_ACCESS_TEAM_DOMAIN": "team.cloudflareaccess.com",
            "STATS19_ACCESS_AUD": "abc",
        }
    )
    assert (s.access_team_domain, s.access_aud) == ("team.cloudflareaccess.com", "abc")
