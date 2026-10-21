"""Similar authorities from open measures (PLAN-009 §10.3).

ONS's area classification covers districts, not the shire counties that are highway
authorities, and CIPFA's nearest-neighbour list isn't open. So, as CIPFA does, each
authority's peers are its nearest neighbours on a few standardised measures: population
(size: a county isn't like a small borough of the same density), population density,
vehicle-km per head, the share of vehicle-km on major roads, and road length per head.

Peers come from the same **country** (England outside London, London, Wales, Scotland):
collisions are recorded at very different rates in each (per vehicle-km Scotland records
about half England's), so a cross-border peer says more about recording than safety (FU-047).

**Recording gaps:** an authority-year whose share of GB collisions falls far below its share
in the years either side is flagged (e.g. B&NES 2023: 76 collisions against ~190 either side,
in DfT's own file). Rates leave flagged years out.

Pure functions, unit-tested without a database.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

PEERS = 15
GAP_RATIO = 0.65  # a year below 65% of the authority's usual share of GB collisions
GAP_WINDOW = 3  # ...judged against the years either side
MIN_GAP_NEIGHBOURS = 3
MIN_GAP_EXPECTED = 30  # collisions a year: smaller authorities are too noisy to judge

Features = tuple[float, float, float, float, float]


@dataclass(frozen=True)
class AuthorityMeasures:
    """Five-year averages for one authority."""

    population: float | None
    area_km2: float | None
    vehicle_km: float | None  # a year, all roads
    major_vehicle_km: float | None
    road_km: float | None


def peer_features(m: AuthorityMeasures) -> Features | None:
    """(log population, log density, log vehicle-km a head, major share, log road km per
    1,000 people), or None when a measure is missing."""
    values = (m.population, m.area_km2, m.vehicle_km, m.major_vehicle_km, m.road_km)
    if any(v is None or v <= 0 for v in values):
        return None
    return (
        math.log(m.population),
        math.log(m.population / m.area_km2),
        math.log(m.vehicle_km / m.population),
        min(1.0, m.major_vehicle_km / m.vehicle_km),
        math.log(1_000 * m.road_km / m.population),
    )


def nearest_peers(
    features: dict[str, Features], k: int = PEERS
) -> dict[str, list[tuple[str, float]]]:
    """Each authority's k nearest others (code, distance), nearest first, on measures
    standardised to mean 0 and standard deviation 1 so none dominates by its scale."""
    codes = sorted(features)
    x = np.array([features[c] for c in codes], dtype=float)
    sd = x.std(axis=0)
    z = (x - x.mean(axis=0)) / np.where(sd > 0, sd, 1.0)
    out: dict[str, list[tuple[str, float]]] = {}
    for i, code in enumerate(codes):
        d = np.sqrt(((z - z[i]) ** 2).sum(axis=1))
        order = sorted((float(d[j]), codes[j]) for j in range(len(codes)) if j != i)
        out[code] = [(c, dist) for dist, c in order[:k]]
    return out


def country_group(region: str | None) -> str:
    """The recording area peers are chosen within: 'scotland', 'wales', 'london', 'england'."""
    return {"Scotland": "scotland", "Wales": "wales", "London": "london"}.get(
        region or "", "england"
    )


def peers_within_country(
    features: dict[str, Features], regions: dict[str, str | None], k: int = PEERS
) -> dict[str, list[tuple[str, float]]]:
    """Nearest peers among authorities in the same country (standardised within it)."""
    groups: dict[str, dict[str, Features]] = {}
    for code, f in features.items():
        groups.setdefault(country_group(regions.get(code)), {})[code] = f
    out: dict[str, list[tuple[str, float]]] = {}
    for group in groups.values():
        out |= nearest_peers(group, k)
    return out


def recording_gaps(
    counts: dict[int, int],
    gb: dict[int, int],
    ratio: float = GAP_RATIO,
    window: int = GAP_WINDOW,
    min_expected: float = MIN_GAP_EXPECTED,
) -> dict[int, float]:
    """Years whose share of GB collisions is below ``ratio`` x the median share of the
    ``window`` years either side, as {year: share / neighbours' share}.

    Neighbours, not the whole series, so a steady trend (Scotland's long decline) isn't a gap;
    shares of GB, so a national dip (2020) isn't either. Authorities too small to judge (the
    neighbours' share would give under ``min_expected`` collisions) are left alone."""
    shares = {y: counts.get(y, 0) / gb[y] for y in sorted(gb) if gb[y] > 0}
    out = {}
    for year, share in shares.items():
        near = [s for y, s in shares.items() if y != year and abs(y - year) <= window]
        if len(near) < MIN_GAP_NEIGHBOURS:
            continue
        usual = float(np.median(near))
        if usual * gb[year] < min_expected:
            continue
        if share / usual < ratio:
            out[year] = share / usual
    return out
