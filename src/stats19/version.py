"""Which code is running (FU-050): the git commit and build date baked into the image.

Docker builds pass them in (scripts/update.sh sets GIT_COMMIT and BUILD_DATE); a dev
checkout or a plain ``docker compose build`` reports "unknown".
"""

from __future__ import annotations

import os


def version() -> dict[str, str | None]:
    return {
        "commit": os.environ.get("STATS19_COMMIT") or "unknown",
        "built": os.environ.get("STATS19_BUILT") or None,
    }
