"""The before/after evaluation (PLAN-011 §3): worked examples, and synthetic sites with a
known effect, so the methods are checked without a database."""

from datetime import date

import numpy as np
import pytest

from stats19.api.scheme_periods import Period
from stats19.evaluation import (
    MIN_AFTER_MONTHS,
    Result,
    calibration_factors,
    clip,
    comparison_group,
    describe,
    eb_before_after,
    eb_group,
    fyrr_pct,
    months_of,
    period_prediction,
    verdict,
    year_fractions,
    years_of,
)

# ---------------------------------------------------------------- periods and calibration


def test_year_fractions_split_a_period_by_days():
    f = year_fractions(Period(date(2021, 7, 1), date(2023, 6, 30)))
    assert f[2021] == pytest.approx(184 / 365)
    assert f[2022] == 1.0
    assert f[2023] == pytest.approx(181 / 365)


def test_year_fractions_count_leap_years_by_their_366_days():
    assert year_fractions(Period(date(2024, 1, 1), date(2024, 1, 31))) == {
        2024: pytest.approx(31 / 366)
    }


def test_clip_keeps_only_the_part_with_data():
    p = Period(date(2023, 7, 1), date(2026, 6, 30))
    assert clip(p, date(2024, 12, 31)) == Period(date(2023, 7, 1), date(2024, 12, 31))
    assert clip(p, date(2023, 6, 30)) is None
    assert months_of(clip(p, date(2024, 12, 31))) == 18
    assert months_of(None) == 0


def test_calibration_factors_are_observed_over_predicted_per_year():
    c = calibration_factors({2020: 800, 2021: 900, 2022: 950}, {2020: 1000, 2021: 1000})
    assert c == {2020: 0.8, 2021: 0.9}


def test_period_prediction_weights_each_year_by_its_share_and_factor():
    spf = {2021: 2.0, 2022: 2.2, 2023: 2.4}
    cal = {2021: 0.9, 2022: 1.0}
    mu = period_prediction(spf, cal, Period(date(2021, 7, 1), date(2023, 6, 30)))
    # 2023 has no factor yet: it borrows 2022's
    expected = 2.0 * 0.9 * 184 / 365 + 2.2 * 1.0 + 2.4 * 1.0 * 181 / 365
    assert mu == pytest.approx(expected)


def test_a_year_before_the_factors_begin_borrows_the_earliest():
    mu = period_prediction(
        {2014: 1.0}, {2016: 0.8, 2017: 0.9}, Period(date(2014, 1, 1), date(2014, 12, 31))
    )
    assert mu == pytest.approx(0.8)


def test_without_any_factors_the_model_is_used_as_it_is():
    mu = period_prediction({2014: 1.5}, {}, Period(date(2014, 1, 1), date(2014, 12, 31)))
    assert mu == pytest.approx(1.5)


def test_period_prediction_needs_the_model_for_every_year():
    with pytest.raises(ValueError, match="2023"):
        period_prediction({2022: 1.0}, {}, Period(date(2022, 1, 1), date(2023, 1, 31)))


# ---------------------------------------------------------------- method A: EB, worked


def test_eb_worked_example():
    """By hand: N_B = 12, N_A = 5, μ_B = 6, μ_A = 6.6 (a 10% upward trend), α = 0.2.

    w = 1/(1 + 0.2·6) = 0.4545; EB_B = 0.4545·6 + 0.5455·12 = 9.2727
    π = 9.2727 · 1.1 = 10.2; Var(π) = 10.2 · 1.1 · 0.5455 = 6.12
    θ = (5/10.2) / (1 + 6.12/10.2²) = 0.49020 / 1.05882 = 0.46296
    Var(θ) = 0.46296² · (1/5 + 0.05882) / 1.05882² = 0.049483 → ±0.43600
    """
    r = eb_before_after(12, 5, 6.0, 6.6, 0.2)

    assert r.method == "eb"
    assert r.expected_after == pytest.approx(10.2)
    assert r.theta == pytest.approx(0.462963, abs=1e-6)
    assert r.lower == pytest.approx(0.462963 - 0.436000, abs=1e-4)
    assert r.upper == pytest.approx(0.462963 + 0.436000, abs=1e-4)
    assert r.change_pct == pytest.approx(-53.7037, abs=1e-3)
    assert r.saved == pytest.approx(5.2)


def test_eb_takes_out_regression_to_the_mean():
    """A site picked after a bad spell (12 against 6 expected) that then has an ordinary
    6: a naive before/after says −50%; EB says the fall is mostly what was expected."""
    naive = 6 / 12
    r = eb_before_after(12, 6, 6.0, 6.0, 0.2)
    assert r.theta > naive + 0.1
    assert r.lower < 1.0 < r.upper


def test_eb_with_no_collisions_after_uses_the_poisson_bound():
    r = eb_before_after(10, 0, 5.0, 5.0, 0.3)
    assert r.theta == 0.0 and r.lower == 0.0
    assert 0.3 < r.upper < 1.0


def test_eb_group_of_one_matches_the_single_site():
    one = eb_before_after(12, 5, 6.0, 6.6, 0.2)
    group = eb_group([(12, 5, 6.0, 6.6, 0.2)])
    assert (group.theta, group.lower, group.upper) == pytest.approx(
        (one.theta, one.lower, one.upper)
    )


@pytest.mark.parametrize(
    "args",
    [(5, 5, 0.0, 1.0, 0.2), (5, 5, 1.0, 0.0, 0.2), (-1, 5, 1.0, 1.0, 0.2), (5, 5, 1.0, 1.0, -1)],
)
def test_eb_refuses_impossible_inputs(args):
    with pytest.raises(ValueError):
        eb_before_after(*args)


def test_eb_group_needs_sites():
    with pytest.raises(ValueError):
        eb_group([])


# ---------------------------------------------------------------- method A: synthetic sites


def _simulate(effect: float, seed: int = 7, sites: int = 40_000):
    """Sites whose true means vary around the model's μ (gamma, as the NB model assumes).
    The worst before-period records are "treated", as schemes are, and the treatment
    multiplies the true after mean by ``effect`` on top of a 10% upward trend."""
    rng = np.random.default_rng(seed)
    mu_b, trend, alpha = 6.0, 1.1, 0.3
    true_b = rng.gamma(1 / alpha, alpha * mu_b, sites)
    n_b = rng.poisson(true_b)
    picked = n_b >= 12  # chosen for a high count: the source of regression to the mean
    n_a = rng.poisson(true_b[picked] * trend * effect)
    group = [
        (int(b), int(a), mu_b, mu_b * trend, alpha) for b, a in zip(n_b[picked], n_a, strict=True)
    ]
    naive = n_a.sum() / (n_b[picked].sum() * trend)
    return eb_group(group), naive


@pytest.mark.parametrize("effect", [0.7, 1.0])
def test_eb_recovers_a_known_effect_on_sites_chosen_for_bad_records(effect):
    result, naive = _simulate(effect)

    assert result.theta == pytest.approx(effect, abs=0.03)
    assert result.lower < effect < result.upper
    # a naive before/after, corrected for the trend only, overstates the benefit a lot
    assert naive < effect - 0.15


# ---------------------------------------------------------------- method B: comparison group


def test_comparison_group_worked_example():
    """K = 20 → L = 10 at the scheme; M = 400 → N = 380 in the comparison area.

    θ = (10/20)/(380/400) = 0.52632; SE(ln θ) = √(1/20 + 1/10 + 1/400 + 1/380) = 0.39387
    CI = 0.52632 · e^(±1.95996 · 0.39387) = 0.2432 to 1.1389
    """
    r = comparison_group(20, 10, 400, 380)

    assert r.method == "comparison"
    assert r.theta == pytest.approx(0.526316, abs=1e-6)
    assert (r.lower, r.upper) == pytest.approx((0.24322, 1.13893), abs=1e-4)
    assert r.expected_after == pytest.approx(19.0)


def test_comparison_group_with_a_zero_uses_haldanes_correction():
    r = comparison_group(8, 0, 300, 290)
    assert r.theta == pytest.approx((0.5 / 8.5) / (290.5 / 300.5))
    # 8 to none is striking, but so few that "no change" is still inside the interval
    assert r.lower < 1.0 < r.upper
    assert verdict(r, 36) == "no_evidence"


@pytest.mark.parametrize("cells", [(0, 0, 10, 10), (5, 5, 0, 0), (-1, 2, 3, 4)])
def test_comparison_group_refuses_what_it_cant_compare(cells):
    with pytest.raises(ValueError):
        comparison_group(*cells)


# ---------------------------------------------------------------- in words


def _result(theta, lower, upper, method="eb"):
    return Result(method, theta, lower, upper, 10.0, 16.0)


def test_a_clear_fall_is_described_with_its_interval():
    r = _result(0.62, 0.44, 0.88)
    assert verdict(r, 24) == "fewer"
    assert describe(r, 24) == (
        "Collisions fell by 38% (95% CI 12% to 56%) compared with what was expected "
        "without the scheme."
    )


def test_a_clear_rise_is_described_too():
    r = _result(1.5, 1.1, 2.0)
    assert verdict(r, 36) == "more"
    assert describe(r, 36).startswith("Collisions rose by 50% (95% CI 10% to 100%)")


def test_an_interval_spanning_no_change_is_not_enough_evidence():
    r = _result(0.8, 0.5, 1.2)
    assert verdict(r, 36) == "no_evidence"
    assert describe(r, 36) == "Not enough evidence of a change yet."


def test_too_little_after_data_is_too_early_whatever_it_shows():
    r = _result(0.3, 0.1, 0.5)
    assert verdict(r, MIN_AFTER_MONTHS - 1) == "too_early"
    assert "11 months" in describe(r, 11)


def test_the_comparison_method_warns_about_regression_to_the_mean():
    text = describe(_result(0.6, 0.4, 0.9, method="comparison"), 36)
    assert "comparison area" in text and "regression to the mean" in text


# ---------------------------------------------------------------- value


def test_years_of_a_period_counts_its_days():
    assert years_of(Period(date(2021, 7, 1), date(2024, 6, 30))) == pytest.approx(3.0, abs=0.003)


def test_fyrr_is_a_years_saving_over_the_cost():
    assert fyrr_pct(1.5, 100_000, 250_000) == pytest.approx(60.0)
    with pytest.raises(ValueError):
        fyrr_pct(1.5, 100_000, 0)
