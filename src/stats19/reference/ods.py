"""Minimal OpenDocument spreadsheet reader (stdlib only) for small DfT tables."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

_NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
_REPEAT = f"{{{_NS['table']}}}number-columns-repeated"
_VALUE = f"{{{_NS['office']}}}value"
_NAME = f"{{{_NS['table']}}}name"
# Trailing empty cells can be "repeated" thousands of times; cap expansion.
_MAX_REPEAT = 64

Cell = float | str | None


def _cell_value(cell: ET.Element) -> Cell:
    if (num := cell.get(_VALUE)) is not None:
        return float(num)
    text = " ".join(p.text or "" for p in cell.iterfind("text:p", _NS)).strip()
    return text or None


def read_ods_sheet(path: Path, sheet: str) -> list[list[Cell]]:
    """Rows of one sheet; numbers as float, text as str, blanks as None."""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("content.xml"))
    for table in root.iter(f"{{{_NS['table']}}}table"):
        if table.get(_NAME) != sheet:
            continue
        rows = []
        for row in table.iterfind("table:table-row", _NS):
            values: list[Cell] = []
            for cell in row:
                repeat = min(int(cell.get(_REPEAT, "1")), _MAX_REPEAT)
                values.extend([_cell_value(cell)] * repeat)
            while values and values[-1] is None:
                values.pop()
            rows.append(values)
        return rows
    raise KeyError(f"sheet {sheet!r} not found in {path.name}")
