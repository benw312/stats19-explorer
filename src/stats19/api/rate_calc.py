"""Authority rates and benchmarking arithmetic (PLAN-009 §10). Pure functions.

Every rate is annual: casualties over the years that have the denominator, divided by the
denominator summed over the same years (person-years, vehicle-km, road-km-years). So an
authority missing a year of traffic (Cumbria's successors before 2023) is still compared
like for like.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import chi2

INTERVAL_BELOW = 100  # counts under this show a 95% interval
_Z = 0.05


@dataclass(frozen=True)
class Counts:
    """Casualties in one authority and year, by the police first road class."""

    major: int  # motorway, A(M), A
    minor: int  # B, C, unclassified
    other: int  # road class not recorded
    ksi: float  # on DfT's adjusted severity: fatal + each casualty's probability of serious

    @property
    def total(self) -> int:
        return self.major + self.minor + self.other


@dataclass(frozen=True)
class Denominators:
    population: float | None
    vehicle_km: float | None
    major_vehicle_km: float | None
    minor_vehicle_km: float | None
    road_km: float | None


@dataclass(frozen=True)
class Rate:
    value: float | None
    count: int  # rounded: adjusted KSI is a sum of probabilities
    low: float | None = None
    high: float | None = None


_NONE = Counts(0, 0, 0, 0)

# rate name -> (numerator, denominator field, scale)
_RATES = {
    "per_100m_vkm": ("total", "vehicle_km", 1e8),
    "ksi_per_100m_vkm": ("ksi", "vehicle_km", 1e8),
    "major_per_100m_vkm": ("major", "major_vehicle_km", 1e8),
    "minor_per_100m_vkm": ("minor", "minor_vehicle_km", 1e8),
    "per_100k_pop": ("total", "population", 1e5),
    "ksi_per_100k_pop": ("ksi", "population", 1e5),
    "per_100km_road": ("total", "road_km", 1e2),
}
RATE_NAMES = tuple(_RATES)


def poisson_interval(count: int) -> tuple[float, float]:
    """Exact 95% interval for a Poisson count (Garwood)."""
    low = 0.0 if count == 0 else chi2.ppf(_Z / 2, 2 * count) / 2
    return float(low), float(chi2.ppf(1 - _Z / 2, 2 * count + 2) / 2)


def _rate(count: float, exposure: float, scale: float) -> Rate:
    whole = round(count)
    if exposure <= 0:
        return Rate(None, whole)
    value = count / exposure * scale
    if whole >= INTERVAL_BELOW:
        return Rate(value, whole)
    low, high = poisson_interval(whole)
    return Rate(value, whole, low / exposure * scale, high / exposure * scale)


def rates(counts: dict[int, Counts], denominators: dict[int, Denominators]) -> dict[str, Rate]:
    """Each rate over the years that have its denominator."""
    return pooled_rates([(counts, denominators)])


Group = tuple[dict[int, Counts], dict[int, Denominators]]


def pooled_rates(groups: list[Group], years: set[int] | None = None) -> dict[str, Rate]:
    """Rates for several authorities together (a region, GB, or one year of them): each
    authority-year adds its casualties only where it has the rate's denominator, so an
    authority missing a year of traffic doesn't inflate the total's vehicle-km rate."""
    out = {}
    for name, (numerator, field, scale) in _RATES.items():
        count, exposure = 0.0, 0.0
        for counts, denominators in groups:
            for year, d in denominators.items():
                value = getattr(d, field)
                if value is None or (years is not None and year not in years):
                    continue
                c = counts.get(year, _NONE)
                count += c.total if numerator == "total" else getattr(c, numerator)
                exposure += value
        out[name] = _rate(count, exposure, scale)
    return out


def peer_summary(values: list[float | None]) -> tuple[float, float, float] | None:
    """(median, lower quartile, upper quartile) of the peers' rates."""
    known = [v for v in values if v is not None]
    if not known:
        return None
    q1, median, q3 = np.percentile(known, [25, 50, 75])
    return float(median), float(q1), float(q3)


def rank_of(value: float | None, others: list[float | None]) -> tuple[int, int] | None:
    """(rank, out of) among itself and the others, 1 = the lowest rate."""
    if value is None:
        return None
    known = [v for v in others if v is not None]
    return 1 + sum(v < value for v in known), len(known) + 1
