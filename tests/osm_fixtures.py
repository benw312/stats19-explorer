"""A tiny OSM extract (PBF) of junction nodes around the road fixture (tests/road_fixtures.py).

Junction signals on the Mill Lane / B3212 junction node (P3), a pedestrian crossing signal
beside it, one by the A30 at N2, a node that isn't a signal, and one signal on a single
approach to the roundabout (more likely a pedestrian crossing: not signalised), and a
mini-roundabout on the Church Road / Bridge Street junction (Z2), which OS maps as a plain
junction. Coordinates are WGS84 for BNG points.
"""

from __future__ import annotations

import functools
import tempfile
from pathlib import Path

import osmium

NODES = [
    (101, -3.5222157, 50.7248917, {"highway": "traffic_signals"}),
    (102, -3.5223822, 50.7247816, {"highway": "traffic_signals", "crossing": "traffic_signals"}),
    (103, -3.5327077, 50.7220832, {"highway": "traffic_signals", "traffic_signals": "crossing"}),
    (104, -3.53, 50.72, {"highway": "crossing"}),
    (105, -3.4901562, 50.7450732, {"highway": "traffic_signals"}),
    (106, -3.4756756, 50.7542596, {"highway": "mini_roundabout"}),
]


def pbf_file(path: Path) -> Path:
    writer = osmium.SimpleWriter(str(path))
    try:
        for node_id, lon, lat, tags in NODES:
            writer.add_node(
                osmium.osm.mutable.Node(id=node_id, version=1, location=(lon, lat), tags=tags)
            )
    finally:
        writer.close()
    return path


@functools.cache
def osm_pbf() -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        return pbf_file(Path(tmp) / "gb.osm.pbf").read_bytes()
