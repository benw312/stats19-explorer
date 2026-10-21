"""scripts/redact.py: diagnostics never carry secrets (FU-050)."""

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "redact.py"
spec = importlib.util.spec_from_file_location("redact", SCRIPT)
redact_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(redact_mod)

ENV = """\
# a comment with PASSWORD=not-a-value
POSTGRES_PASSWORD=fake-db-password-123
STATS19_API_DB_PASSWORD='quoted-secret-value'
CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiYWJjIn0abcdefghijk
STATS19_ACCESS_AUD=0123456789abcdef
WEB_BIND=0.0.0.0
STATS19_API_DB_USER=stats19_api
EMPTY_PASSWORD=
"""


def test_secret_values_are_the_secret_settings_only():
    values = redact_mod.secret_values(ENV)

    assert set(values) == {
        "fake-db-password-123",
        "quoted-secret-value",
        "eyJhIjoiYWJjIn0abcdefghijk",
    }


def test_redact_removes_secrets_wherever_they_appear():
    text = (
        "connecting with fake-db-password-123\n"
        "STATS19_DATABASE_URL=postgresql://stats19:other-pw@db:5432/stats19\n"
        "tunnel token eyJhIjoiYWJjIn0abcdefghijk\n"
        "Cf-Access-Jwt-Assertion: eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJl\n"
        "aud 0123456789abcdef bind 0.0.0.0\n"
    )

    out = redact_mod.redact(text, redact_mod.secret_values(ENV))

    for secret in ("fake-db-password-123", "other-pw", "eyJhIjoi", "eyJhbGci", "c2lnbmF0dXJl"):
        assert secret not in out
    assert "postgresql://stats19:•••@db:5432" in out
    assert "aud 0123456789abcdef bind 0.0.0.0" in out  # not secret: kept


def test_the_script_filters_stdin(tmp_path):
    env = tmp_path / ".env"
    env.write_text(ENV)

    out = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(env)],
        input="password is quoted-secret-value\n",
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    assert out == "password is •••\n"
