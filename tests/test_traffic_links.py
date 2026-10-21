"""Pure parts of count point -> OS link matching: overlap trimming, snapping, claims."""

import pytest

from stats19.reference.traffic_links import (
    MinorPoint,
    Piece,
    resolve_claims,
    road_length_m,
    snap,
    trim_overlaps,
    with_rescues,
)


def piece(cp, a, b, d=10.0, link="L1"):
    return Piece(link, cp, a, b, d)


def spans(pieces):
    return sorted((p.count_point_id, round(p.frac_from, 3), round(p.frac_to, 3)) for p in pieces)


def test_disjoint_pieces_are_kept():
    got = trim_overlaps([piece(1, 0.0, 0.4), piece(2, 0.4, 1.0)])

    assert spans(got) == [(1, 0.0, 0.4), (2, 0.4, 1.0)]


def test_overlap_goes_to_the_nearer_dft_line():
    got = trim_overlaps([piece(2, 0.5, 1.0, d=30.0), piece(1, 0.0, 0.6, d=5.0)])

    assert spans(got) == [(1, 0.0, 0.6), (2, 0.6, 1.0)]


def test_contained_piece_splits_the_container_when_nearer():
    far_whole = piece(1, 0.0, 1.0, d=80.0)
    near_inner = piece(2, 0.2, 0.5, d=5.0)

    assert spans(trim_overlaps([far_whole, near_inner])) == [
        (1, 0.0, 0.2),
        (1, 0.5, 1.0),
        (2, 0.2, 0.5),
    ]


def test_contained_piece_loses_to_a_nearer_container():
    got = trim_overlaps([piece(1, 0.0, 1.0, d=5.0), piece(2, 0.2, 0.5, d=80.0)])

    assert spans(got) == [(1, 0.0, 1.0)]


def test_coincident_dft_lines_tie_break_on_the_count_point_location():
    main = Piece("L1", 1, 0.0, 1.0, dist_m=40.2, point_m=90.0)
    slip = Piece("L1", 2, 0.0, 1.0, dist_m=39.8, point_m=3.0)

    assert spans(trim_overlaps([main, slip])) == [(2, 0.0, 1.0)]


def test_gaps_between_pieces_stay_unclaimed():
    got = trim_overlaps([piece(1, 0.0, 0.3), piece(2, 0.6, 1.0)])

    assert spans(got) == [(1, 0.0, 0.3), (2, 0.6, 1.0)]


def test_links_are_trimmed_independently_and_slivers_dropped():
    got = trim_overlaps(
        [
            piece(1, 0.0, 0.5, link="A"),
            piece(2, 0.0, 1.0, link="B"),
            piece(3, 0.0, 0.0005, link="C"),
        ],
        min_frac=0.001,
    )

    assert sorted((p.link_id, p.count_point_id) for p in got) == [("A", 1), ("B", 2)]


def test_rescued_piece_takes_its_stretch_from_a_nearer_dft_line():
    # FU-034 #1: count point 2 lost every piece to 1's line, but sits on 0.4-0.6 itself
    owner = piece(1, 0.0, 1.0, d=5.0)
    rescued = Piece("L1", 2, 0.4, 0.6, dist_m=40.0, rescued=True)

    assert spans(with_rescues([owner], [rescued])) == [(1, 0.0, 0.4), (1, 0.6, 1.0), (2, 0.4, 0.6)]


def test_rescue_never_leaves_another_count_point_without_a_link():
    owner = piece(1, 0.4, 0.6, d=5.0)
    rescued = Piece("L1", 2, 0.3, 0.7, dist_m=40.0, rescued=True)
    elsewhere = Piece("L2", 3, 0.0, 1.0, dist_m=40.0, rescued=True)

    assert spans(with_rescues([owner], [rescued, elsewhere])) == [(1, 0.4, 0.6), (3, 0.0, 1.0)]


def row(id, road_class, number, t, d):
    # id, class, number, name, start, end, length, fraction, distance
    return (id, road_class, number, None, "s", "e", 100.0, t, d)


B_POINT = MinorPoint(1, "B3212", "MB", False, 0.0, 0.0)
U_POINT = MinorPoint(2, "U", "MCU", False, 0.0, 0.0)


def test_snap_prefers_the_matching_b_road_number_over_a_closer_link():
    rows = [row("near", "B Road", "B3174", 0.5, 2.0), row("right", "B Road", "B3212", 0.3, 12.0)]

    link, fraction, distance = snap(rows, B_POINT)

    assert (link.id, fraction, distance) == ("right", 0.3, 12.0)


def test_snap_prefers_the_expected_class_for_unclassified_points():
    rows = [
        row("c", "Classified Unnumbered", None, 0.5, 3.0),
        row("u", "Unclassified", None, 0.5, 9.0),
    ]

    assert snap(rows, U_POINT)[0].id == "u"


def test_snap_nothing_nearby():
    assert snap([], U_POINT) is None


def test_resolve_claims_prefers_current_then_nearest():
    claims = [
        (10, True, {"x": 0.0, "y": 50.0}),  # historic count point, nearest to x
        (20, False, {"x": 300.0, "z": 10.0}),  # current
        (30, False, {"y": 20.0, "z": 400.0}),
    ]

    assert resolve_claims(claims) == {"x": (20, 300.0), "y": (30, 20.0), "z": (20, 10.0)}


@pytest.mark.parametrize(
    ("road", "category", "first"),
    [("B1", "MB", "B Road"), ("C", "MCU", "Classified Unnumbered"), ("U", "MCU", "Unclassified")],
)
def test_expected_class_order(road, category, first):
    from stats19.reference.traffic_links import _expected_classes

    assert _expected_classes(MinorPoint(1, road, category, False, 0, 0))[0] == first


@pytest.mark.parametrize(
    ("single", "dual", "dft", "expected"),
    [
        (1000, 0, 1000, 1000),  # single carriageway
        (0, 2000, 1000, 1000),  # both carriageways traced: halve
        (0, 1000, 1000, 1000),  # one carriageway traced: don't halve (FU-047 #4)
        (400, 1200, 1000, 1000),  # mixed, both carriageways on the dual part
        (400, 600, 1000, 1000),  # mixed, one carriageway
        (0, 2000, None, 1000),  # no DfT length (minor roads): halve, as before
    ],
)
def test_road_length_halves_dual_pieces_only_when_both_carriageways_are_traced(
    single, dual, dft, expected
):
    assert road_length_m(single, dual, dft) == pytest.approx(expected)
