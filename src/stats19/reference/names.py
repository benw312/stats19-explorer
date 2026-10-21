"""OS Open Names: places, roads and selected features for search (OGL)."""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

SOURCE_URL = (
    "https://api.os.uk/downloads/v1/products/OpenNames/downloads?area=GB&format=CSV&redirect"
)

# Postcodes come from Code-Point Open instead; landcover/hydrography aren't useful here.
KEEP_LOCAL_TYPES = frozenset(
    {
        "City",
        "Town",
        "Village",
        "Hamlet",
        "Suburban Area",
        "Other Settlement",
        "Named Road",
        "Numbered Road",
        "Section Of Numbered Road",
        "Primary Education",
        "Secondary Education",
        "Special Needs Education",
        "Further Education",
        "Higher or University Education",
        "Non State Primary Education",
        "Non State Secondary Education",
        "Hospital",
        "Railway Station",
        "Bus Station",
    }
)

# Column positions in the headerless data files (Doc/OS_Open_Names_Header.csv).
_ID, _NAME1, _LOCAL_TYPE, _X, _Y = 0, 2, 7, 8, 9
_XMIN, _YMIN, _XMAX, _YMAX = 12, 13, 14, 15
_POPULATED_PLACE, _DISTRICT, _COUNTY = 18, 21, 24

NameRow = tuple[str, str, str, str | None, str | None, str | None, int, int, int, int, int, int]


def _int(value: str, default: int) -> int:
    return int(float(value)) if value else default


def parse_names(path: Path) -> Iterator[NameRow]:
    """(id, name, local_type, populated_place, district, county, x, y, xmin, ymin, xmax, ymax)."""
    with zipfile.ZipFile(path) as z:
        names = sorted(n for n in z.namelist() if n.startswith("Data/") and n.endswith(".csv"))
        for name in names:
            with z.open(name) as raw:
                for row in csv.reader(io.TextIOWrapper(raw, encoding="utf-8-sig")):
                    if len(row) <= _COUNTY or row[_LOCAL_TYPE] not in KEEP_LOCAL_TYPES:
                        continue
                    x, y = _int(row[_X], 0), _int(row[_Y], 0)
                    yield (
                        row[_ID],
                        row[_NAME1],
                        row[_LOCAL_TYPE],
                        row[_POPULATED_PLACE] or None,
                        row[_DISTRICT] or None,
                        row[_COUNTY] or None,
                        x,
                        y,
                        _int(row[_XMIN], x),
                        _int(row[_YMIN], y),
                        _int(row[_XMAX], x),
                        _int(row[_YMAX], y),
                    )
