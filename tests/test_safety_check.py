"""The safety model's out-of-sample check (FU-038 #8): picking and scoring the worst sites."""

import pytest

from stats19.reference.safety_build import UNIT_COLUMNS
from stats19.reference.safety_check import as_sites, compare_periods, format_results

COLUMNS = [c.strip() for c in UNIT_COLUMNS.split(",")]


def site(uid, *, observed, predicted, excess, rank, size=100, region="england", unit="junction"):
    values = {c: None for c in COLUMNS} | {
        "unit_type": unit,
        "unit_id": uid,
        "region": region,
        "observed": observed,
        "predicted": predicted,
        "excess": excess,
        "excess_rank": rank,
        "group_size": size,
    }
    return tuple(values[c] for c in COLUMNS)


def test_methods_pick_differently_and_are_scored_next_period():
    before = as_sites(
        [
            # many collisions, but as expected for its traffic
            site("busy", observed=40, predicted=38, excess=1, rank=40),
            # worse than similar sites
            site("bad", observed=12, predicted=4, excess=6, rank=1),
            # quiet: a high ratio on tiny numbers
            site("quiet", observed=2, predicted=0.2, excess=0.5, rank=30),
        ]
        + [site(f"x{i}", observed=1, predicted=1, excess=0, rank=50 + i) for i in range(47)]
    )
    after = as_sites(
        [
            site("busy", observed=39, predicted=38, excess=0.5, rank=45),
            site("bad", observed=10, predicted=4, excess=5, rank=2),
            site("quiet", observed=0, predicted=0.2, excess=-0.1, rank=90),
        ]
        + [site(f"x{i}", observed=1, predicted=1, excess=0, rank=50 + i) for i in range(47)]
    )

    results = {r.method: r for r in compare_periods(before, after, top_share=0.02)}

    # 2% of 50 sites = 1 pick per method
    assert {m: r.sites for m, r in results.items()} == dict.fromkeys(results, 1)
    assert results["eb_region"].next_excess == 5  # picked "bad"; it stayed bad
    assert results["count"].next_observed == 39  # picked "busy"
    assert results["rate"].next_excess == pytest.approx(-0.1)  # picked "quiet": noise
    assert results["eb_region"].stayed_worse == 1.0
    assert results["rate"].stayed_worse == 0.0


def test_regional_ranking_spreads_picks_across_regions():
    # London records more, so its excesses are bigger; ranked within region, each region's
    # worst site is picked
    rows = [
        site("L1", observed=30, predicted=10, excess=15, rank=1, size=2, region="london"),
        site("L2", observed=28, predicted=10, excess=14, rank=2, size=2, region="london"),
        site("S1", observed=6, predicted=2, excess=3, rank=1, size=2, region="scotland"),
        site("S2", observed=1, predicted=2, excess=-1, rank=2, size=2, region="scotland"),
    ]
    sites = as_sites(rows)

    results = {r.method: r for r in compare_periods(sites, sites, top_share=0.5)}

    assert results["eb_region"].region_share == {"london": 0.5, "scotland": 0.5}
    assert results["eb_national"].region_share == {"london": 1.0}


def test_unmodelled_or_vanished_sites_are_left_out():
    before = as_sites(
        [
            site("gone", observed=9, predicted=1, excess=8, rank=1),
            site("unmodelled", observed=9, predicted=None, excess=None, rank=None),
            site("kept", observed=3, predicted=1, excess=2, rank=2),
        ]
    )
    after = as_sites([site("kept", observed=2, predicted=1, excess=1, rank=1)])

    [first, *_] = compare_periods(before, after, top_share=0.5)

    assert first.sites == 1 and first.next_observed == 2


def test_format_results_is_a_markdown_table():
    sites = as_sites([site("a", observed=3, predicted=1, excess=2, rank=1)])
    text = format_results((2016, 2020), (2021, 2025), compare_periods(sites, sites))

    assert text.startswith("Ranked on 2016-2020; outcome in 2021-2025")
    assert "| junction | eb_region | 1 |" in text
