"""Junction rules (PLAN-008 T3) on small hand-built examples: node clustering, arms, types."""

import pytest

from stats19.reference.junctions import (
    ArmLink,
    arm_roles,
    classify,
    cluster_nodes,
    group_arms,
    junction_name,
)


def arm(
    link, bearing, number=None, name=None, road_class="Unclassified", form="Single Carriageway"
):
    return ArmLink(link, road_class, number, name, form, bearing)


# ------------------------------------------------------------------ clustering


def test_nodes_joined_by_a_short_link_are_one_junction():
    nodes = {"a": (0, 0), "b": (20, 0), "c": (500, 0)}

    got = cluster_nodes(nodes, ring_edges=[], short_edges=[("a", "b", 20.0)])

    assert got == {"a": "a", "b": "a"}  # c is a junction on its own, so not listed


def test_short_links_cannot_chain_a_street_into_one_junction():
    # junction nodes every 25 m along a street: merging stops once the span passes 60 m
    nodes = {f"n{i}": (25 * i, 0) for i in range(6)}
    edges = [(f"n{i}", f"n{i + 1}", 25.0) for i in range(5)]

    got = cluster_nodes(nodes, [], edges)

    spans = {}
    for node, cluster in got.items():
        spans.setdefault(cluster, []).append(nodes[node][0])
    assert all(max(xs) - min(xs) <= 60 for xs in spans.values())
    assert len(spans) >= 2


def test_ring_links_form_one_roundabout_and_take_nearby_split_nodes():
    ring = {"r1": (0, 50), "r2": (50, 0), "r3": (0, -50), "r4": (-50, 0)}
    nodes = ring | {"s": (75, 0), "far": (300, 0)}
    ring_edges = [("r1", "r2"), ("r2", "r3"), ("r3", "r4"), ("r4", "r1")]

    got = cluster_nodes(nodes, ring_edges, [("r2", "s", 25.0)])

    assert set(got) == {"r1", "r2", "r3", "r4", "s"}
    assert len(set(got.values())) == 1
    assert got["s"] == "r1"  # cluster id: the smallest node id


# ------------------------------------------------------------------ arms


def test_dual_carriageway_pair_is_one_arm_but_each_side_of_a_through_road_is_its_own():
    links = [
        arm("west", 270, "A30", road_class="A Road"),
        arm("east", 90, "A30", road_class="A Road"),
        arm("side-in", 355, name="Mill Lane"),
        arm("side-out", 10, name="Mill Lane"),
    ]

    arms = group_arms(links)

    assert sorted(len(a.links) for a in arms) == [1, 1, 2]
    assert classify(arms, ring=False, mini=False) == "t_junction"


def test_bearings_wrap_round_north():
    arms = group_arms([arm("a", 355, "B1"), arm("b", 5, "B1"), arm("c", 180, "B1")])

    assert len(arms) == 2


def test_unnamed_links_are_separate_arms():
    arms = group_arms([arm("a", 0), arm("b", 10), arm("c", 180)])

    assert len(arms) == 3


@pytest.mark.parametrize(
    ("bearings", "ring", "mini", "kind"),
    [
        ((0, 120, 240), True, False, "roundabout"),
        ((0, 90, 180, 270), False, True, "mini_roundabout"),
        ((0, 90, 180), False, False, "t_junction"),
        ((0, 90, 180, 270), False, False, "crossroads"),
        ((0, 70, 140, 210, 280), False, False, "multi_arm"),
        ((0, 180), False, False, None),  # a carriageway split, not a junction
        ((0, 180), True, False, None),  # a turning circle
    ],
)
def test_classify(bearings, ring, mini, kind):
    arms = group_arms([arm(f"l{i}", b, name=f"Road {i}") for i, b in enumerate(bearings)])

    assert classify(arms, ring=ring, mini=mini) == kind


def test_merge_and_diverge_stay_with_the_link():
    # a slip road leaving the M5: the junction is where the slip road ends, not here
    arms = group_arms(
        [
            arm("m-south", 180, "M5", road_class="Motorway"),
            arm("m-north", 0, "M5", road_class="Motorway"),
            arm("slip", 30, road_class="Unclassified", form="Slip Road"),
        ]
    )

    assert classify(arms, ring=False, mini=False) is None


def test_slip_roads_splitting_inside_an_interchange_are_not_a_junction():
    arms = group_arms(
        [
            arm("in", 180, "M25", road_class="Motorway", form="Slip Road"),
            arm("left", 300, "A3", road_class="A Road", form="Slip Road"),
            arm("right", 60, "A3", road_class="A Road", form="Slip Road"),
        ]
    )

    assert classify(arms, ring=False, mini=False) is None


def test_slip_road_ending_at_a_priority_junction_is_a_junction():
    arms = group_arms(
        [
            arm("a-west", 270, "A38", road_class="A Road"),
            arm("a-east", 90, "A38", road_class="A Road"),
            arm("slip", 0, "M5", road_class="Motorway", form="Slip Road"),
        ]
    )

    assert classify(arms, ring=False, mini=False) == "t_junction"


# ------------------------------------------------------------------ names and roles


def test_name_lists_roads_by_class_then_label():
    arms = group_arms(
        [
            arm("u", 0, name="Mill Lane"),
            arm("b", 90, "B3212", road_class="B Road"),
            arm("a1", 180, "A38", road_class="A Road"),
            arm("a2", 270, "A38", road_class="A Road"),
            arm("x", 45),
        ]
    )

    assert junction_name(arms) == "A38 / B3212 / Mill Lane"


def test_name_of_an_unnamed_junction():
    assert junction_name(group_arms([arm("a", 0), arm("b", 120), arm("c", 240)])) is None


def test_roles_major_is_the_top_road_both_sides():
    arms = group_arms(
        [
            arm("a1", 90, "A38", road_class="A Road"),
            arm("side", 0, "B3212", road_class="B Road"),
            arm("a2", 270, "A38", road_class="A Road"),
        ]
    )

    roles = {a.links[0].link_id: r for a, r in zip(arms, arm_roles(arms), strict=True)}

    assert roles == {"a1": "major", "a2": "major", "side": "minor"}


def test_roles_unnamed_top_road_is_only_one_arm():
    arms = group_arms([arm("a", 0), arm("b", 120), arm("c", 240)])

    assert arm_roles(arms).count("major") == 1
