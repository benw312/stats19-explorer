"""OSM junction nodes: which nodes are read, and signals vs crossings vs mini-roundabouts."""

import pytest

from stats19.reference.osm_nodes import node_kind, parse_osm_nodes

from .osm_fixtures import pbf_file


def test_reads_signal_and_mini_roundabout_nodes(tmp_path):
    got = list(parse_osm_nodes(pbf_file(tmp_path / "gb.osm.pbf")))

    assert [(i, kind) for i, kind, _, _ in got] == [
        (101, "signals"),
        (102, "crossing_signals"),
        (103, "crossing_signals"),
        (105, "signals"),
        (106, "mini_roundabout"),
    ]
    assert got[0][2:] == pytest.approx((-3.5222157, 50.7248917))


@pytest.mark.parametrize(
    ("tags", "kind"),
    [
        ({"highway": "traffic_signals"}, "signals"),
        ({"highway": "traffic_signals", "traffic_signals": "signal"}, "signals"),
        ({"highway": "traffic_signals", "crossing": "no"}, "signals"),
        ({"highway": "traffic_signals", "crossing": "traffic_signals"}, "crossing_signals"),
        ({"highway": "traffic_signals", "crossing": "marked"}, "crossing_signals"),
        ({"highway": "traffic_signals", "traffic_signals": "crossing"}, "crossing_signals"),
        ({"highway": "traffic_signals", "traffic_signals": "blinker"}, "crossing_signals"),
        ({"highway": "mini_roundabout"}, "mini_roundabout"),
    ],
)
def test_node_kind(tags, kind):
    assert node_kind(tags) == kind
