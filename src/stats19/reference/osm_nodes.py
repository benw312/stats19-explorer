"""OpenStreetMap junction nodes (ODbL): traffic signals and mini-roundabouts.

OS Open Roads records neither junction control nor most mini-roundabouts, and STATS19
records control only where a collision happened, so peer groups need another source
(PLAN-008 T3a). OSM tags:

- ``highway=traffic_signals``: a set of signals. Those that only control a pedestrian
  crossing carry a ``crossing`` tag (or ``traffic_signals=crossing``); we keep them, marked
  ``crossing_signals``, so only junction signals make a junction signalised.
- ``highway=mini_roundabout``: the painted or domed central island, on the junction node.

Read from Geofabrik's Great Britain extract with pyosmium: one pass over nodes with a tag
filter, a few seconds for GB. (Whole-country Overpass queries are discouraged and often
time out.)
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import osmium

SOURCE_URL = "https://download.geofabrik.de/europe/great-britain-latest.osm.pbf"
ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"
SIGNALS, CROSSING_SIGNALS, MINI_ROUNDABOUT = "signals", "crossing_signals", "mini_roundabout"
_CROSSING_ONLY = {"crossing", "blinker", "emergency"}


def node_kind(tags: dict[str, str]) -> str:
    """'mini_roundabout', 'signals' (junction signals) or 'crossing_signals'."""
    if tags.get("highway") == "mini_roundabout":
        return MINI_ROUNDABOUT
    if tags.get("traffic_signals") in _CROSSING_ONLY:
        return CROSSING_SIGNALS
    if tags.get("crossing", "no") != "no":
        return CROSSING_SIGNALS
    return SIGNALS


def parse_osm_nodes(path: Path) -> Iterator[tuple[int, str, float, float]]:
    """(osm id, kind, lon, lat) for every traffic signals and mini-roundabout node."""
    processor = osmium.FileProcessor(str(path), osmium.osm.NODE).with_filter(
        osmium.filter.TagFilter(("highway", "traffic_signals"), ("highway", "mini_roundabout"))
    )
    for node in processor:
        if not node.location.valid():
            continue
        tags = {t.k: t.v for t in node.tags}
        yield node.id, node_kind(tags), node.location.lon, node.location.lat
