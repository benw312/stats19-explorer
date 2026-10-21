"""Collision -> OS road link scoring (PLAN-008 T3b), after DfT's 2026 feasibility method."""

import pytest

from stats19.reference.collision_links import (
    Candidate,
    CollisionRoad,
    best_match,
    levenshtein,
    police_road_number,
    score,
)


def cand(link="L", d=5.0, road_class="A Road", number="A30", form="Single Carriageway"):
    return Candidate(link, d, road_class, number, form)


A30 = CollisionRoad(road_class=3, road_number=30, road_type=6)


@pytest.mark.parametrize(
    ("road_class", "number", "expected"),
    [
        (1, 5, "M5"),
        (2, 1, "A1(M)"),
        (3, 30, "A30"),
        (4, 3212, "B3212"),
        (5, 0, None),
        (6, -1, None),
        (3, 0, None),
    ],
)
def test_police_road_number(road_class, number, expected):
    assert police_road_number(road_class, number) == expected


def test_levenshtein():
    assert levenshtein("A30", "A30") == 0
    assert levenshtein("A30", "A38") == 1
    assert levenshtein("A30", "A303") == 1
    assert levenshtein("B3212", "A30") == 4


def test_close_exact_match_scores_over_100():
    assert score(A30, cand(d=3)) >= 100


def test_number_beats_distance():
    near_wrong = cand("near", d=2, number="A361")
    far_right = cand("far", d=20, number="A30")

    assert best_match(A30, [near_wrong, far_right]).link_id == "far"


def test_typo_in_number_scores_between_exact_and_wrong():
    exact = score(A30, cand(number="A30"))
    typo = score(A30, cand(number="A303"))
    wrong = score(A30, cand(number="B3212", road_class="B Road"))

    assert exact > typo > wrong


def test_unnumbered_roads_match_unnumbered_links():
    lane = CollisionRoad(road_class=6, road_number=0, road_type=6)
    numbered = cand("a", d=4, number="A30")
    street = cand("u", d=9, number=None, road_class="Unclassified")

    assert best_match(lane, [numbered, street]).link_id == "u"


@pytest.mark.parametrize("police_class", [5, 6])  # C, unclassified
def test_police_c_or_u_label_doesnt_pull_a_collision_to_a_further_minor_road(police_class):
    # FU-037 #2: officers' C/U labels are often wrong; OS decides the class, so between
    # minor roads the nearer one wins.
    road = CollisionRoad(road_class=police_class, road_number=0, road_type=6)
    near_c = cand("c", d=4, number=None, road_class="Classified Unnumbered")
    near_u = cand("u", d=4, number=None, road_class="Unclassified")
    far_c = cand("far_c", d=12, number=None, road_class="Classified Unnumbered")
    far_u = cand("far_u", d=12, number=None, road_class="Unclassified")

    assert best_match(road, [near_u, far_c]).link_id == "u"
    assert best_match(road, [near_c, far_u]).link_id == "c"
    assert score(road, near_c) == score(road, near_u)


def test_police_c_label_gets_no_class_points_on_a_b_road():
    road = CollisionRoad(road_class=5, road_number=0, road_type=6)
    b_road = cand("b", d=4, number=None, road_class="B Road")
    c_road = cand("c", d=4, number=None, road_class="Classified Unnumbered")

    assert score(road, c_road) > score(road, b_road)


def test_m6_toll_special_case():
    m6 = CollisionRoad(road_class=1, road_number=6, road_type=3)
    toll = cand(number="M6 TOLL", road_class="Motorway", form="Dual Carriageway")

    assert score(m6, toll) >= 100


def test_form_of_way_separates_slip_road_from_main_carriageway():
    slip = CollisionRoad(road_class=1, road_number=5, road_type=7)
    main = cand("main", d=6, number="M5", road_class="Motorway", form="Dual Carriageway")
    ramp = cand("ramp", d=9, number="M5", road_class="Motorway", form="Slip Road")

    assert best_match(slip, [main, ramp]).link_id == "ramp"


def test_roundabout_collision_prefers_the_ring():
    rbt = CollisionRoad(road_class=3, road_number=30, road_type=1)
    arm = cand("arm", d=5)
    ring = cand("ring", d=8, form="Roundabout")

    assert best_match(rbt, [arm, ring]).link_id == "ring"


def test_ties_go_to_the_nearer_link_then_id():
    got = best_match(A30, [cand("b", d=5), cand("a", d=5), cand("c", d=4)])

    assert got.link_id == "c"
    assert best_match(A30, []) is None


def test_match_records_the_runner_up_margin():
    got = best_match(A30, [cand("a", d=2), cand("b", d=10, number="A38")])

    assert got.score == score(A30, cand("a", d=2))
    assert got.margin == pytest.approx(got.score - score(A30, cand("b", d=10, number="A38")))
    assert best_match(A30, [cand("a")]).margin is None
