"""DfT RAS4001: average value of prevention per reported collision/casualty."""

from __future__ import annotations

from pathlib import Path

from stats19.reference.ods import read_ods_sheet

DATA_TABLES_API = "https://www.gov.uk/api/content/government/statistical-data-sets/road-safety-statistics-data-tables"
SHEET = "Average_value"

PreventionRow = tuple[int, int, str, float | None, float | None]


def _num(value) -> float | None:
    return value if isinstance(value, float) else None


def parse_prevention(path: Path) -> list[PreventionRow]:
    """(data_year, price_year, severity, per_casualty, per_collision) from Average_value."""
    rows = read_ods_sheet(path, SHEET)
    header_at = next(
        (i for i, r in enumerate(rows) if r and str(r[0]).startswith("Collision data year")),
        None,
    )
    if header_at is None:
        raise ValueError(f"{path.name}: header row not found in {SHEET}")
    out = []
    for r in rows[header_at + 1 :]:
        if len(r) < 5 or not isinstance(r[0], float):
            continue
        out.append((int(r[0]), int(r[1]), str(r[2]), _num(r[3]), _num(r[4])))
    return out
