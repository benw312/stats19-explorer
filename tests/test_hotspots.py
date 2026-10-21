"""Greedy cluster-circle site finding (PLAN-005 §2): pure Python, no database."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from stats19.hotspots import HotspotParams, Point, binomial_sf, find_sites

FATAL, SERIOUS, SLIGHT = 1, 2, 3


def pt(
    i: int, x: float, y: float, severity: int = SLIGHT, rural: bool = False, value: float = 0.0
) -> Point:
    return Point(id=f"C{i:04d}", x=x, y=y, severity=severity, rural=rural, year=2023, value=value)


def group(start: int, cx: float, cy: float, n: int, spread: float = 5.0, **kw) -> list[Point]:
    """n points on a small ring around (cx, cy)."""
    return [
        pt(
            start + k,
            cx + spread * math.cos(2 * math.pi * k / n),
            cy + spread * math.sin(2 * math.pi * k / n),
            **kw,
        )
        for k in range(n)
    ]


def ids(site) -> set[str]:
    return {p.id for p in site.members}


def test_two_tight_urban_groups_30m_apart_are_one_site():
    # 30 m apart is inside one 50 m circle: one site takes all ten
    pts = group(0, 0, 0, 5) + group(10, 30, 0, 5)
    sites = find_sites(pts, HotspotParams())
    assert len(sites) == 1
    assert len(sites[0].members) == 10


def test_urban_groups_120m_apart_are_two_sites():
    pts = group(0, 0, 0, 5) + group(10, 120, 0, 6)
    sites = find_sites(pts, HotspotParams())
    assert [len(s.members) for s in sites] == [6, 5]  # ranked: bigger first
    assert [s.rank for s in sites] == [1, 2]


def test_rural_radius_is_wider_than_urban():
    # 80 m apart: two urban sites, but one rural site (100 m radius)
    urban = find_sites(group(0, 0, 0, 5) + group(10, 80, 0, 5), HotspotParams())
    rural = find_sites(
        group(0, 0, 0, 5, rural=True) + group(10, 80, 0, 5, rural=True), HotspotParams()
    )
    assert len(urban) == 2
    assert len(rural) == 1 and len(rural[0].members) == 10
    assert rural[0].radius_m == 100 and urban[0].radius_m == 50


def test_corridor_splits_into_sites_no_wider_than_the_circle():
    # a 2 km road with a collision every 10 m: chains forever under DBSCAN
    pts = [pt(i, i * 10.0, 0) for i in range(201)]
    sites = find_sites(pts, HotspotParams(max_sites=200))
    assert len(sites) >= 15
    for s in sites:
        xs = [p.x for p in s.members]
        assert max(xs) - min(xs) <= 2 * s.radius_m
    used = [p.id for s in sites for p in s.members]
    assert len(used) == len(set(used))  # no collision in two sites


def test_ksi_qualifies_a_small_site():
    pts = [pt(0, 0, 0, SERIOUS), pt(1, 10, 0, FATAL), pt(2, 500, 0), pt(3, 505, 0)]
    sites = find_sites(pts, HotspotParams())
    assert len(sites) == 1
    assert ids(sites[0]) == {"C0000", "C0001"}
    assert sites[0].ksi == 2


def test_below_both_thresholds_is_not_a_site():
    assert find_sites(group(0, 0, 0, 4), HotspotParams()) == []
    assert find_sites(group(0, 0, 0, 4), HotspotParams(min_collisions=4))[0].collisions == 4


def test_ksi_weighted_score_ranks_severity_over_volume():
    slight_six = group(0, 0, 0, 6)
    ksi_five = group(10, 1000, 0, 5, severity=SERIOUS)
    weighted = find_sites(slight_six + ksi_five, HotspotParams())
    by_count = find_sites(slight_six + ksi_five, HotspotParams(score="count"))
    assert weighted[0].ksi == 5 and weighted[0].score == 15
    assert by_count[0].collisions == 6 and by_count[0].score == 6


def test_value_score_uses_point_values():
    cheap = group(0, 0, 0, 6, value=10.0)
    dear = group(10, 1000, 0, 5, value=100.0)
    sites = find_sites(cheap + dear, HotspotParams(score="value"))
    assert sites[0].score == pytest.approx(500.0)


def test_max_sites_limits_output():
    pts = [p for k in range(5) for p in group(k * 10, k * 1000.0, 0, 5)]
    assert len(find_sites(pts, HotspotParams(max_sites=3))) == 3


def test_ties_are_deterministic():
    pts = group(0, 0, 0, 5) + group(10, 1000, 0, 5)
    first = [ids(s) for s in find_sites(pts, HotspotParams())]
    again = [ids(s) for s in find_sites(list(reversed(pts)), HotspotParams())]
    assert first == again


def test_site_summary_fields():
    pts = group(0, 100, 200, 5, spread=4.0)
    (site,) = find_sites(pts, HotspotParams())
    assert site.fatal == 0 and site.serious == 0 and site.slight == 5
    assert site.cx == pytest.approx(100, abs=1e-6) and site.cy == pytest.approx(200, abs=1e-6)
    assert site.centre.id in ids(site)


def test_empty_input():
    assert find_sites([], HotspotParams()) == []


def test_params_are_validated():
    with pytest.raises(ValidationError):
        HotspotParams(radius_urban_m=5)
    with pytest.raises(ValidationError):
        HotspotParams(score="vibes")
    with pytest.raises(ValidationError):
        HotspotParams(unknown=1)


@pytest.mark.parametrize(
    ("k", "n", "p", "expected"),
    [
        (0, 10, 0.3, 1.0),
        (10, 10, 0.5, 0.5**10),
        (3, 5, 0.2, 0.05792),  # 1 - P(X<=2)
        (6, 20, 0.1, 0.01125),
        (1, 1, 0.0, 0.0),
        (1, 1, 1.0, 1.0),
    ],
)
def test_binomial_sf(k, n, p, expected):
    assert binomial_sf(k, n, p) == pytest.approx(expected, abs=1e-5)


def test_ksi_weight_uses_the_adjusted_probability_when_given():
    # FU-047 #10: forces record serious injuries differently; DfT's adjusted severity gives
    # each collision a probability of being KSI. Weight = 1 + 2 x that probability.
    slight_but_likely_serious = [
        Point(id=f"S{i}", x=0, y=0, severity=3, rural=False, year=2023, p_ksi=0.5)
        for i in range(5)  # the default minimum for a site
    ]

    site = find_sites(slight_but_likely_serious, HotspotParams())[0]

    assert site.score == pytest.approx(5 * 2.0)
    assert site.ksi == 0  # the KSI count stays as recorded
