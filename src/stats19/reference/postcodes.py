"""OS Code-Point Open: GB postcode unit centroids (OGL)."""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

SOURCE_URL = (
    "https://api.os.uk/downloads/v1/products/CodePointOpen/downloads?area=GB&format=CSV&redirect"
)

PostcodeRow = tuple[str, str, int, str | None, int, int]


def postcode_key(postcode: str) -> str:
    """Upper-case with all whitespace removed: ' ex1  1ae ' -> 'EX11AE'."""
    return "".join(postcode.split()).upper()


def parse_postcodes(path: Path) -> Iterator[PostcodeRow]:
    """(postcode, key, positional_quality, admin_district_code, easting, northing).

    Postcodes with no grid reference (quality 90, 0/0) are skipped.
    """
    with zipfile.ZipFile(path) as z:
        names = sorted(n for n in z.namelist() if n.startswith("Data/CSV/") and n.endswith(".csv"))
        for name in names:
            with z.open(name) as raw:
                for row in csv.reader(io.TextIOWrapper(raw, encoding="utf-8")):
                    if len(row) < 9:
                        continue
                    easting, northing = int(row[2]), int(row[3])
                    if easting == 0 and northing == 0:
                        continue
                    yield (
                        row[0].strip(),
                        postcode_key(row[0]),
                        int(row[1]),
                        row[8].strip() or None,
                        easting,
                        northing,
                    )
