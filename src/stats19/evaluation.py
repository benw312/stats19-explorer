"""Did a scheme work? The before/after evaluation (PLAN-011 §3), as pure functions.

Two methods, chosen by site type:

- **A. Empirical Bayes (EB) before/after** for junctions and links with a safety model.
  It corrects for regression to the mean and the general trend (Hauer, *Observational
  Before–After Studies in Road Safety*, 1997, ch. 6 and 9).
- **B. Comparison group** for areas, routes, clusters and sites without a model: the
  change at the scheme against the change elsewhere, as an odds ratio. It corrects for the
  trend but **not** for regression to the mean, and the wording says so.

Both give θ, the index of effectiveness: the after count as a share of what was expected
without the scheme. θ = 0.62 means 38% fewer collisions than expected. The database work
(counting, calibration factors per year, the site's model) lives elsewhere and passes its
numbers in, so every rule here is unit-tested on worked examples.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

from stats19.api.scheme_periods import Period, months_between
from stats19.reference.safety import empirical_bayes

Z95 = 1.959963984540054
# The 95% upper limit of a Poisson mean when none were seen (−ln 0.025)
POISSON_UPPER_ZERO = 3.6888794541139363
# Below this many months of after-data, the result is "too early" whatever it shows
MIN_AFTER_MONTHS = 12

Method = Literal["eb", "comparison"]
Verdict = Literal["fewer", "more", "no_evidence", "too_early"]


@dataclass(frozen=True)
class Result:
    method: Method
    #: Index of effectiveness: after ÷ expected without the scheme (1 = no change)
    theta: float
    lower: float  # 95% confidence interval for θ
    upper: float
    #: Collisions after, and those expected without the scheme over the same period
    observed_after: float
    expected_after: float

    @property
    def change_pct(self) -> float:
        """The % change: −38 means 38% fewer than expected."""
        return 100.0 * (self.theta - 1.0)

    @property
    def saved(self) -> float:
        """Collisions saved over the after period (negative when there were more)."""
        return self.expected_after - self.observed_after


# ---------------------------------------------------------------- periods and calibration


def year_fractions(period: Period) -> dict[int, float]:
    """How much of each calendar year the period covers, by days: 1 Jul–31 Dec 2021 is
    {2021: 0.504}. The SPF and the calibration are yearly, so a part-year counts in part."""
    out: dict[int, float] = {}
    for year in range(period.start.year, period.end.year + 1):
        first = max(period.start, date(year, 1, 1))
        last = min(period.end, date(year, 12, 31))
        days_in_year = (date(year + 1, 1, 1) - date(year, 1, 1)).days
        out[year] = ((last - first).days + 1) / days_in_year
    return out


def clip(period: Period, data_end: date) -> Period | None:
    """The part of a period that has data, or None when none has arrived yet."""
    if period.start > data_end:
        return None
    return Period(period.start, min(period.end, data_end))


def calibration_factors(
    observed: Mapping[int, float], predicted: Mapping[int, float]
) -> dict[int, float]:
    """Observed ÷ predicted collisions for the whole peer group, per year: the general
    trend the model, fitted on pooled years, doesn't know about. Years without a
    prediction are left out."""
    return {
        y: observed.get(y, 0.0) / predicted[y]
        for y in predicted
        if predicted[y] > 0 and y in observed
    }


def period_prediction(
    spf_per_year: Mapping[int, float], calibration: Mapping[int, float], period: Period
) -> float:
    """μ for a period: the site's yearly SPF prediction (from that year's flow) times the
    year's calibration factor, weighted by the share of the year the period covers.

    A year with no calibration factor borrows the nearest earlier one (the newest year,
    before the group's counts are in), else the earliest (a year before the collision
    matches begin); with no factors at all, 1.
    """
    total = 0.0
    for year, share in year_fractions(period).items():
        if year not in spf_per_year:
            raise ValueError(f"no safety-model prediction for {year}")
        total += spf_per_year[year] * _factor(calibration, year) * share
    return total


def _factor(calibration: Mapping[int, float], year: int) -> float:
    if year in calibration:
        return calibration[year]
    if not calibration:
        return 1.0
    earlier = [y for y in calibration if y < year]
    return calibration[max(earlier) if earlier else min(calibration)]


# ---------------------------------------------------------------- method A: Empirical Bayes


def eb_before_after(
    n_before: int, n_after: int, mu_before: float, mu_after: float, alpha: float
) -> Result:
    """Hauer's EB before/after for one site.

    1. Combine the model's μ_B with the site's own N_B: EB_B = w·μ_B + (1 − w)·N_B, with
       w = 1 / (1 + α·μ_B). That's the before count with the chance high taken out.
    2. Carry it into the after period with the model's ratio: π = EB_B · μ_A / μ_B, the
       collisions expected after without the scheme. Var(π) = π · (μ_A/μ_B) · (1 − w).
    3. θ = (λ/π) / (1 + Var(π)/π²), with λ = N_A, and
       Var(θ) = θ² (Var(λ)/λ² + Var(π)/π²) / (1 + Var(π)/π²)², Var(λ) = λ.

    With no collisions after, the formula's variance breaks down, so the upper limit uses
    the Poisson bound for a zero count instead.
    """
    if mu_before <= 0 or mu_after <= 0:
        raise ValueError("the model must predict some collisions in both periods")
    if n_before < 0 or n_after < 0 or alpha < 0:
        raise ValueError("counts and α can't be negative")
    eb, _, w = empirical_bayes(n_before, mu_before, alpha)
    ratio = mu_after / mu_before
    pi = eb * ratio
    var_pi = pi * ratio * (1.0 - w)
    return _theta(float(n_after), pi, var_pi, "eb")


def eb_group(sites: list[tuple[int, int, float, float, float]]) -> Result:
    """EB for several sites treated together (e.g. a route's links): sum λ, π and Var(π)
    over the sites (Hauer's four steps), then one θ. Each site is
    (n_before, n_after, μ_before, μ_after, α)."""
    if not sites:
        raise ValueError("no sites to evaluate")
    lam = pi = var_pi = 0.0
    for n_b, n_a, mu_b, mu_a, alpha in sites:
        one = eb_before_after(n_b, n_a, mu_b, mu_a, alpha)
        eb, _, w = empirical_bayes(n_b, mu_b, alpha)
        ratio = mu_a / mu_b
        lam += one.observed_after
        pi += one.expected_after
        var_pi += eb * ratio * ratio * (1.0 - w)
    return _theta(lam, pi, var_pi, "eb")


def _theta(lam: float, pi: float, var_pi: float, method: Method) -> Result:
    if pi <= 0:
        raise ValueError("nothing expected after: can't evaluate")
    shrink = 1.0 + var_pi / pi**2
    theta = (lam / pi) / shrink
    if lam > 0:
        var_theta = theta**2 * (1.0 / lam + var_pi / pi**2) / shrink**2
        half = Z95 * math.sqrt(var_theta)
        lower, upper = max(0.0, theta - half), theta + half
    else:
        lower, upper = 0.0, (POISSON_UPPER_ZERO / pi) / shrink
    return Result(method, theta, lower, upper, lam, pi)


# ---------------------------------------------------------------- method B: comparison group


def comparison_group(
    treated_before: int, treated_after: int, comparison_before: int, comparison_after: int
) -> Result:
    """The odds ratio of the change at the scheme against the change in the comparison
    area over the same periods: θ = (L/K) / (N/M), with K, L the scheme's before and after
    counts and M, N the comparison area's.

    The CI is from the log odds ratio, Var(ln θ) ≈ 1/K + 1/L + 1/M + 1/N. Any zero count
    takes half a collision in every cell (Haldane's correction) so θ stays finite.
    """
    cells = (treated_before, treated_after, comparison_before, comparison_after)
    if min(cells) < 0:
        raise ValueError("counts can't be negative")
    if comparison_before == 0 and comparison_after == 0:
        raise ValueError("the comparison area has no collisions: can't compare")
    if treated_before == 0 and treated_after == 0:
        raise ValueError("no collisions at the scheme in either period: can't compare")
    k, l_, m, n = (c + 0.5 for c in cells) if 0 in cells else (float(c) for c in cells)
    theta = (l_ / k) / (n / m)
    se = math.sqrt(1 / k + 1 / l_ + 1 / m + 1 / n)
    lower, upper = theta * math.exp(-Z95 * se), theta * math.exp(Z95 * se)
    # what the scheme would have had after, changing as the comparison area did
    expected = treated_before * (comparison_after / comparison_before) if comparison_before else 0.0
    return Result("comparison", theta, lower, upper, float(treated_after), expected)


# ---------------------------------------------------------------- in words


def verdict(result: Result, after_months: int) -> Verdict:
    if after_months < MIN_AFTER_MONTHS:
        return "too_early"
    if result.upper < 1.0:
        return "fewer"
    if result.lower > 1.0:
        return "more"
    return "no_evidence"


def describe(result: Result, after_months: int) -> str:
    """The headline, in plain words, as the result card shows it."""
    v = verdict(result, after_months)
    if v == "too_early":
        return (
            f"Too early to tell: {after_months} months of after-data so far, and at least "
            f"{MIN_AFTER_MONTHS} are needed."
        )
    if v == "no_evidence":
        return "Not enough evidence of a change yet."
    # θ's CI, turned into a % change: the upper θ is the smaller fall
    if v == "fewer":
        lo, hi = _pct(1 - result.upper), _pct(1 - result.lower)
        head = f"Collisions fell by {_pct(-result.change_pct / 100)}% (95% CI {lo}% to {hi}%)"
    else:
        lo, hi = _pct(result.lower - 1), _pct(result.upper - 1)
        head = f"Collisions rose by {_pct(result.change_pct / 100)}% (95% CI {lo}% to {hi}%)"
    if result.method == "eb":
        return f"{head} compared with what was expected without the scheme."
    return (
        f"{head} compared with the change in the comparison area. This doesn't allow for "
        "regression to the mean: if the site was picked after a bad spell, part of the fall "
        "would have happened anyway."
    )


def _pct(share: float) -> int:
    return round(100 * share)


def months_of(period: Period | None) -> int:
    """Whole months in a (clipped) period, for "14 of 36 months"."""
    return 0 if period is None else months_between(period.start, period.end)


# ---------------------------------------------------------------- value


def years_of(period: Period) -> float:
    """The period's length in years, for collisions a year."""
    return ((period.end - period.start).days + 1) / 365.25


def fyrr_pct(collisions_saved_a_year: float, value_per_collision: float, cost: float) -> float:
    """First-year rate of return: a year's saving as a % of the cost."""
    if cost <= 0:
        raise ValueError("the cost must be positive")
    return 100.0 * collisions_saved_a_year * value_per_collision / cost
