"""Authority rates and benchmarking arithmetic (PLAN-009 §10)."""

import pytest

from stats19.api.rate_calc import (
    Counts,
    Denominators,
    peer_summary,
    pooled_rates,
    rank_of,
    rates,
)


def test_rates_are_annual_and_use_only_years_with_each_denominator():
    counts = {
        2024: Counts(major=60, minor=40, other=0, ksi=20),
        2025: Counts(major=50, minor=50, other=0, ksi=30),
    }
    denominators = {
        2024: Denominators(
            population=100_000,
            vehicle_km=None,
            major_vehicle_km=None,
            minor_vehicle_km=None,
            road_km=1_000,
        ),
        2025: Denominators(
            population=100_000,
            vehicle_km=1e9,
            major_vehicle_km=4e8,
            minor_vehicle_km=6e8,
            road_km=1_000,
        ),
    }

    got = rates(counts, denominators)

    # population and road length: both years (person-years, road-km-years)
    assert got["per_100k_pop"].value == pytest.approx(100.0)
    assert got["per_100k_pop"].count == 200
    assert got["ksi_per_100k_pop"].value == pytest.approx(25.0)
    assert got["per_100km_road"].value == pytest.approx(10.0)
    # vehicle-km: 2025 only (2024 has no traffic, e.g. Cumbria before the split)
    assert got["per_100m_vkm"].value == pytest.approx(10.0)
    assert got["per_100m_vkm"].count == 100
    assert got["ksi_per_100m_vkm"].value == pytest.approx(3.0)
    assert got["major_per_100m_vkm"].value == pytest.approx(12.5)
    assert got["minor_per_100m_vkm"].value == pytest.approx(50 / 6)


def test_small_counts_carry_a_poisson_interval():
    counts = {2025: Counts(major=4, minor=0, other=0, ksi=1)}
    denominators = {2025: Denominators(100_000, 1e8, 1e8, 0.0, 100.0)}

    got = rates(counts, denominators)

    r = got["per_100k_pop"]
    assert r.value == pytest.approx(4.0)
    assert r.low == pytest.approx(1.0899, abs=1e-3)  # exact Poisson 95% for 4
    assert r.high == pytest.approx(10.2416, abs=1e-3)
    assert got["minor_per_100m_vkm"].value is None  # no minor vehicle-km: no rate


def test_large_counts_have_no_interval():
    counts = {2025: Counts(major=500, minor=500, other=0, ksi=100)}
    denominators = {2025: Denominators(1_000_000, 1e10, 5e9, 5e9, 5_000.0)}

    r = rates(counts, denominators)["per_100k_pop"]

    assert r.low is None and r.high is None


def test_missing_years_and_no_denominators_give_no_rate():
    got = rates({}, {2025: Denominators(None, None, None, None, None)})

    assert all(r.value is None for r in got.values())


def test_peer_summary_gives_median_and_quartiles():
    assert peer_summary([1.0, 2.0, 3.0, 4.0, None]) == pytest.approx((2.5, 1.75, 3.25))
    assert peer_summary([None]) is None


def test_rank_of_counts_from_the_lowest_rate():
    # 1st = lowest rate: the best record among the group
    assert rank_of(2.0, [1.0, 3.0, 4.0, None]) == (2, 4)
    assert rank_of(None, [1.0]) is None


def test_pooled_rates_leave_out_casualties_where_an_authority_has_no_traffic():
    with_traffic = (
        {2025: Counts(major=10, minor=10, other=0, ksi=2)},
        {2025: Denominators(100_000, 1e8, 5e7, 5e7, 100.0)},
    )
    no_traffic = (
        {2025: Counts(major=90, minor=90, other=0, ksi=18)},
        {2025: Denominators(100_000, None, None, None, 100.0)},
    )

    got = pooled_rates([with_traffic, no_traffic])

    assert got["per_100m_vkm"].value == pytest.approx(20.0)  # only the first authority
    assert got["per_100k_pop"].value == pytest.approx(100.0)  # both: 200 / 200k
    assert pooled_rates([with_traffic], years={2024})["per_100k_pop"].value is None
