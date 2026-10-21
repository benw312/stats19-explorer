"""A tiny OS Open Roads GeoPackage around the traffic fixture count points (Exeter, BNG).

A30 (count point 1001, DfT line 291000,92000 -> 292800,93000): two OS links along the line,
    one beyond its end (not claimed) and a slip road (left to the junction).
A38 (count point 1002): one OS link along its line.
Mill Lane (count point 1003, unclassified, at 292500,92800): M1 + M2, then a junction with
    the B3212 at P3 ends the stretch, so M3 beyond it isn't included.
An unnamed C road (count point 1004 at 292200,93400): one link.
A roundabout (four ring links around 295000,95000) where the A377 passes east-west,
    Station Road leaves north and an M5 slip road south; motorway junction "M5 J30" sits
    beside it, and a car park access off it isn't an arm.
"""

from __future__ import annotations

import functools
import sqlite3
import struct
import tempfile
from pathlib import Path

from .traffic_fixtures import zip_bytes

# id, class, form of way, number, name, start, end, coordinates
LINKS = [
    (
        "A30-1",
        "A Road",
        "Single Carriageway",
        "A30",
        None,
        "N1",
        "N2",
        [(291000, 92000), (291900, 92500)],
    ),
    (
        "A30-2",
        "A Road",
        "Single Carriageway",
        "A30",
        None,
        "N2",
        "N3",
        [(291900, 92500), (292800, 93000)],
    ),
    (
        "A30-3",
        "A Road",
        "Single Carriageway",
        "A30",
        None,
        "N3",
        "N4",
        [(292800, 93000), (293500, 93400)],
    ),
    (
        "A30-slip",
        "A Road",
        "Slip Road",
        "A30",
        None,
        "N2",
        "N9",
        [(291900, 92500), (291950, 92600)],
    ),
    (
        "A38-1",
        "A Road",
        "Single Carriageway",
        "A38",
        None,
        "Q1",
        "Q2",
        [(292500, 92500), (293600, 93700)],
    ),
    (
        "M1",
        "Unclassified",
        "Single Carriageway",
        None,
        "Mill Lane",
        "P1",
        "P2",
        [(292400, 92800), (292500, 92800)],
    ),
    (
        "M2",
        "Unclassified",
        "Single Carriageway",
        None,
        "Mill Lane",
        "P2",
        "P3",
        [(292500, 92800), (292650, 92800)],
    ),
    (
        "M3",
        "Unclassified",
        "Single Carriageway",
        None,
        "Mill Lane",
        "P3",
        "P4",
        [(292650, 92800), (292750, 92800)],
    ),
    (
        "B1",
        "B Road",
        "Single Carriageway",
        "B3212",
        None,
        "P3",
        "P5",
        [(292650, 92800), (292650, 93000)],
    ),
    (
        "C1",
        "Classified Unnumbered",
        "Single Carriageway",
        None,
        None,
        "R1",
        "R2",
        [(292100, 93400), (292300, 93400)],
    ),
    # roundabout ring (R = 20 m) and its three arms
    ("RB-1", "A Road", "Roundabout", "A377", None, "K1", "K2", [(295000, 95020), (295020, 95000)]),
    ("RB-2", "A Road", "Roundabout", "A377", None, "K2", "K3", [(295020, 95000), (295000, 94980)]),
    ("RB-3", "A Road", "Roundabout", "A377", None, "K3", "K4", [(295000, 94980), (294980, 95000)]),
    ("RB-4", "A Road", "Roundabout", "A377", None, "K4", "K1", [(294980, 95000), (295000, 95020)]),
    (
        "A377-W",
        "A Road",
        "Single Carriageway",
        "A377",
        None,
        "W1",
        "K4",
        [(294700, 95000), (294980, 95000)],
    ),
    (
        "A377-E",
        "A Road",
        "Single Carriageway",
        "A377",
        None,
        "K2",
        "E1",
        [(295020, 95000), (295300, 95000)],
    ),
    (
        "STN",
        "Unclassified",
        "Single Carriageway",
        None,
        "Station Road",
        "K1",
        "S1",
        [(295000, 95020), (295000, 95300)],
    ),
    (
        "M5-SLIP",
        "Motorway",
        "Slip Road",
        "M5",
        None,
        "K3",
        "J9",
        [(295000, 94980), (295050, 94850)],
    ),
    # Church Road / Bridge Street: a T to OS, a mini-roundabout to OSM
    (
        "CH-1",
        "Unclassified",
        "Single Carriageway",
        None,
        "Church Road",
        "Z1",
        "Z2",
        [(295800, 96000), (296000, 96000)],
    ),
    (
        "CH-2",
        "Unclassified",
        "Single Carriageway",
        None,
        "Church Road",
        "Z2",
        "Z3",
        [(296000, 96000), (296200, 96000)],
    ),
    (
        "BR-1",
        "Unclassified",
        "Single Carriageway",
        None,
        "Bridge Street",
        "Z2",
        "Z4",
        [(296000, 96000), (296000, 96200)],
    ),
    # a shared-space street (no kerbs) is open to traffic, so it's an arm (FU-042)
    (
        "MP-1",
        "Unclassified",
        "Shared Use Carriageway",
        None,
        "Market Place",
        "Z2",
        "Z5",
        [(296000, 96000), (296000, 95800)],
    ),
    # a car park access at the roundabout is not an arm
    (
        "CP",
        "Not Classified",
        "Single Carriageway",
        None,
        None,
        "K3",
        "C9",
        [(295000, 94980), (295000, 94900)],
    ),
]
ACCESS_LINKS = {"CP"}


def _gp(wkb: bytes) -> bytes:
    """GeoPackage geometry: 'GP', version 0, flags (little-endian, no envelope), SRS 27700."""
    return b"GP" + bytes([0, 0b00000001]) + struct.pack("<i", 27700) + wkb


def _line(coords: list[tuple[float, float]]) -> bytes:
    return struct.pack("<BII", 1, 2, len(coords)) + b"".join(
        struct.pack("<dd", x, y) for x, y in coords
    )


def _point(x: float, y: float) -> bytes:
    return struct.pack("<BIdd", 1, 1, x, y)


def gpkg_file(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE road_link (fid INTEGER PRIMARY KEY, geometry BLOB, id TEXT,
               fictitious BOOLEAN, road_classification TEXT, road_function TEXT, form_of_way TEXT,
               road_classification_number TEXT, name_1 TEXT, road_structure TEXT, length REAL,
               trunk_road BOOLEAN, primary_route BOOLEAN, start_node TEXT, end_node TEXT)"""
    )
    conn.execute(
        "CREATE TABLE road_node (fid INTEGER PRIMARY KEY, geometry BLOB, id TEXT, form_of_road_node TEXT)"
    )
    nodes: dict[str, tuple[float, float]] = {}
    for lid, cls, form, number, name, a, b, coords in LINKS:
        length = sum(
            ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            for (x1, y1), (x2, y2) in zip(coords, coords[1:], strict=False)
        )
        conn.execute(
            "INSERT INTO road_link (geometry, id, fictitious, road_classification, road_function, form_of_way,"
            " road_classification_number, name_1, road_structure, length, trunk_road, primary_route,"
            " start_node, end_node) VALUES (?,?,0,?,?,?,?,?,NULL,?,0,0,?,?)",
            (
                _gp(_line(coords)),
                lid,
                cls,
                "Restricted Local Access Road" if lid in ACCESS_LINKS else cls,
                form,
                number,
                name,
                length,
                a,
                b,
            ),
        )
        nodes.setdefault(a, coords[0])
        nodes.setdefault(b, coords[-1])
    # a fictitious link is skipped by the loader
    conn.execute(
        "INSERT INTO road_link (geometry, id, fictitious, road_classification, form_of_way, length, start_node, end_node)"
        " VALUES (?, 'FICT', 1, 'Unknown', 'Single Carriageway', 1, 'X1', 'X2')",
        (_gp(_line([(0, 0), (1, 1)])),),
    )
    for nid, (x, y) in nodes.items():
        conn.execute(
            "INSERT INTO road_node (geometry, id, form_of_road_node) VALUES (?,?,?)",
            (_gp(_point(x, y)), nid, "roundabout" if nid.startswith("K") else "junction"),
        )
    conn.execute(
        "CREATE TABLE motorway_junction (fid INTEGER PRIMARY KEY, geometry BLOB, id TEXT,"
        " junction_number TEXT)"
    )
    conn.execute(
        "INSERT INTO motorway_junction (geometry, id, junction_number) VALUES (?, 'MJ1', 'M5 J30')",
        (_gp(_point(295100, 95100)),),
    )
    conn.commit()
    conn.close()
    return path


@functools.cache
def roads_zip() -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        gpkg = gpkg_file(Path(tmp) / "fixture.gpkg")
        return zip_bytes({"Data/oproad_gb.gpkg": gpkg.read_bytes()})
