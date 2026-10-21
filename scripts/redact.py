#!/usr/bin/env python3
"""Strip secrets from text before it's shared (FU-050; used by scripts/diagnose.sh).

Usage: some-command | scripts/redact.py [.env]

Replaces the values of the secret settings in .env wherever they appear, plus anything
that looks like a password in a database URL or a JWT. Standard library only: it runs
on the host, outside the containers.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SECRET_KEYS = ("PASSWORD", "TOKEN", "SECRET")
MASK = "•••"
PATTERNS = (
    # postgresql://user:password@host
    (re.compile(r"(://[^:/@\s]+:)[^@\s]+@"), rf"\g<1>{MASK}@"),
    # JWTs (Cloudflare Access assertions, tunnel tokens)
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]+){0,2}"), MASK),
)


def secret_values(env_text: str) -> list[str]:
    values = []
    for line in env_text.splitlines():
        key, sep, value = line.strip().partition("=")
        if not sep or key.startswith("#"):
            continue
        value = value.strip().strip("'\"")
        if any(word in key.upper() for word in SECRET_KEYS) and len(value) >= 4:
            values.append(value)
    return sorted(values, key=len, reverse=True)  # longest first: no partial leftovers


def redact(text: str, secrets: list[str]) -> str:
    for value in secrets:
        text = text.replace(value, MASK)
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def main(argv: list[str]) -> int:
    env = Path(argv[1]) if len(argv) > 1 else Path(".env")
    secrets = secret_values(env.read_text()) if env.exists() else []
    for line in sys.stdin:
        sys.stdout.write(redact(line, secrets))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
