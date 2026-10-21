"""OS Open Roads (OGL): GB road links and nodes, read from the GeoPackage without GDAL.

A GeoPackage is SQLite; each geometry is a small 'GP' header plus standard WKB. We turn
that into EWKB (WKB with SRID 27700) so PostGIS can COPY it straight into typed columns.
"""

from __future__ import annotations

import sqlite3
import struct
from collections.abc import Iterator
from pathlib import Path

SOURCE_URL = (
    "https://api.os.uk/downloads/v1/products/OpenRoads/downloads?area=GB&format=GeoPackage&redirect"
)
GPKG_MEMBER_SUFFIX = ".gpkg"
BNG = 27700
_EWKB_SRID_FLAG = 0x20000000
# GeoPackage envelope size in bytes by the flags' envelope indicator (bits 1-3).
_ENVELOPE_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}

# Road hierarchy: a junction with a road of equal or higher rank ends a minor stretch.
CLASS_RANK = {
    "Motorway": 0,
    "A Road": 1,
    "B Road": 2,
    "Classified Unnumbered": 3,
    "Unclassified": 4,
    "Not Classified": 4,
    "Unknown": 5,
}

LINK_COLUMNS = (
    "id",
    "road_class",
    "road_function",
    "form_of_way",
    "road_number",
    "name",
    "structure",
    "length_m",
    "trunk",
    "primary_route",
    "start_node",
    "end_node",
)


def gpkg_to_ewkb(blob: bytes, srid: int = BNG) -> str:
    """Hex EWKB (with SRID) from a GeoPackage geometry blob."""
    if blob[:2] != b"GP":
        raise ValueError("not a GeoPackage geometry")
    flags = blob[3]
    if flags & 0x10:
        raise ValueError("empty geometry")
    envelope = _ENVELOPE_BYTES.get((flags >> 1) & 0x07)
    if envelope is None:
        raise ValueError(f"bad GeoPackage envelope flag in {flags:#x}")
    wkb = blob[8 + envelope :]
    order = "<" if wkb[0] == 1 else ">"
    (geom_type,) = struct.unpack(f"{order}I", wkb[1:5])
    header = wkb[:1] + struct.pack(f"{order}II", geom_type | _EWKB_SRID_FLAG, srid)
    return (header + wkb[5:]).hex()


def _rows(path: Path, query: str) -> Iterator[tuple]:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        yield from conn.execute(query)
    finally:
        conn.close()


def parse_links(path: Path) -> Iterator[tuple]:
    """Road links in LINK_COLUMNS order plus EWKB, fictitious links skipped."""
    query = """SELECT id, road_classification, road_function, form_of_way,
                      road_classification_number, name_1, road_structure, length,
                      trunk_road, primary_route, start_node, end_node, geometry
               FROM road_link WHERE NOT coalesce(fictitious, 0)"""
    for *attrs, trunk, primary, start, end, geom in _rows(path, query):
        yield (*attrs, bool(trunk), bool(primary), start, end, gpkg_to_ewkb(geom))


def parse_nodes(path: Path) -> Iterator[tuple[str, str | None, str]]:
    """(id, form of road node, EWKB) for every node."""
    for node_id, form, geom in _rows(path, "SELECT id, form_of_road_node, geometry FROM road_node"):
        yield node_id, form, gpkg_to_ewkb(geom)


def parse_motorway_junctions(path: Path) -> Iterator[tuple[str, str, str]]:
    """(id, junction number such as 'M5 J30', EWKB point): OS names only these junctions."""
    for junction_id, number, geom in _rows(
        path, "SELECT id, junction_number, geometry FROM motorway_junction"
    ):
        yield junction_id, number, gpkg_to_ewkb(geom)
