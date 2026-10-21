"""Safety performance functions and Empirical Bayes screening (PLAN-008 T4).

HSM Part B, as used in UK practice:

1. a negative binomial (NB2) regression of collisions on flow per peer group: the
   *safety performance function* (SPF), giving each site's predicted collisions;
2. Empirical Bayes: each site's expected collisions blend the prediction with its own count,
   weighted by how much the group varies (HSM eq. 3.36): w = 1 / (1 + alpha * mu);
3. *excess* = EB-expected minus predicted: positive means worse than similar sites carrying
   the same traffic. It is a screening measure (where to look), not proof of a defect.

Peer groups come only from open data (PLAN-008 §10). Pure functions apart from the model
fit, which uses statsmodels.

Regions: collisions per vehicle recorded differ by police reporting area (London's are
several times Scotland's for similar roads). Fitted nationally, every London site looked
"worse" (22% in the worst 5%) and almost no Scottish or Welsh site did. Each model takes
region indicators instead (HSM calibration by jurisdiction), so a site is compared with
similar sites as recorded in its own region.
"""

from __future__ import annotations

import math
import statistics
import warnings
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import numpy as np
import statsmodels.api as sm

URBAN_JUNCTIONS_500M = 18  # junctions within 500 m: 50% of police-recorded collisions urban
MIN_GROUP_SIZE = 100
MIN_REGION_SITES = 30  # sites a region needs within a group to get its own level
REGIONS = ("london", "scotland", "wales")  # baseline: the rest of England

_LINK_CATEGORY = {"TM": "motorway", "PM": "motorway", "TA": "trunk_a", "PA": "principal_a"}


def is_urban(junctions_within_500m: int) -> bool:
    return junctions_within_500m >= URBAN_JUNCTIONS_500M


MIN_TYPICAL_SAMPLES = 30  # counted arms needed for a class and setting's own typical flow
_MINOR_CLASS = {
    "Motorway": "Motorway",
    "A Road": "A Road",
    "B Road": "B Road",
    "Classified Unnumbered": "Classified Unnumbered",
}  # every other OS class (Unclassified, Not Classified, Unknown) is an unclassified road


def typical_minor_flows(
    samples: Iterable[tuple[str | None, bool, float]], min_samples: int = MIN_TYPICAL_SAMPLES
) -> Callable[..., float]:
    """A typical flow (AADF) for an uncounted minor arm, from (OS class, urban, AADF) of the
    counted ones (FU-038 #5): the median for its class and setting, else for its class, else
    for every counted minor arm. DfT's minor counts are a sample of minor roads, so their
    medians stand in for the roads it didn't count."""
    by_cell: dict[tuple[str, bool], list[float]] = defaultdict(list)
    by_class: dict[str, list[float]] = defaultdict(list)
    every: list[float] = []
    for road_class, urban, aadf in samples:
        key = _MINOR_CLASS.get(road_class or "", "Unclassified")
        by_cell[(key, urban)].append(aadf)
        by_class[key].append(aadf)
        every.append(aadf)
    overall = statistics.median(every) if every else 0.0

    def typical(road_class: str | None, urban: bool) -> float:
        key = _MINOR_CLASS.get(road_class or "", "Unclassified")
        for found in (by_cell.get((key, urban), []), by_class.get(key, [])):
            if len(found) >= min_samples:
                return statistics.median(found)
        return overall

    return typical


def region_of(highway_authority: str | None) -> str:
    """'london', 'scotland', 'wales' or 'england' (the baseline) from an ONS authority code."""
    code = highway_authority or ""
    if code.startswith("E09"):
        return "london"
    if code.startswith("S"):
        return "scotland"
    if code.startswith("W"):
        return "wales"
    return "england"


def region_features(region: str) -> dict[str, float]:
    """Indicator per non-baseline region, for the SPF."""
    return {f"region_{r}": 1.0 if region == r else 0.0 for r in REGIONS}


def link_family(road_category: str, dual: bool, urban: bool) -> tuple[str, ...]:
    """Most specific link peer group: (road type, carriageway, urban/rural)."""
    return (
        _LINK_CATEGORY.get(road_category, "other"),
        "dual" if dual else "single",
        "urban" if urban else "rural",
    )


def junction_family(kind: str, signalised: bool | None, urban: bool) -> tuple[str, ...]:
    """Most specific junction peer group: (type and control, urban/rural)."""
    if kind in ("roundabout", "mini_roundabout"):
        family = kind
    elif signalised:
        family = "signals"
    elif kind == "t_junction":
        family = "priority_t"
    else:
        family = "priority_cross"
    return (family, "urban" if urban else "rural")


def assign_groups(families: list[tuple[str, ...]], min_size: int = MIN_GROUP_SIZE) -> list[str]:
    """Each site's peer group: its full family, or a shorter prefix when the group is small."""
    labels = list(families)
    for depth in range(max((len(f) for f in families), default=0), 1, -1):
        sizes = Counter(f[:depth] for f in labels if len(f) == depth)
        labels = [f[: depth - 1] if len(f) == depth and sizes[f] < min_size else f for f in labels]
    return ["/".join(f) for f in labels]


@dataclass(frozen=True)
class Spf:
    intercept: float
    coefficients: dict[str, float]
    alpha: float  # NB2 overdispersion
    n: int
    mean_observed: float
    log_likelihood: float = 0.0
    features: tuple[str, ...] = field(default=())

    def predict(self, x: dict[str, float], offset: float = 0.0) -> float:
        eta = self.intercept + offset + sum(self.coefficients[k] * x[k] for k in self.features)
        return math.exp(eta)


_FIT_METHODS = ("newton", "bfgs", "nm")


def _start_params(y: np.ndarray, exog: np.ndarray, offset: np.ndarray) -> np.ndarray:
    """Poisson coefficients plus a moment estimate of alpha: a sound place to start NB2."""
    poisson = sm.GLM(y, exog, offset=offset, family=sm.families.Poisson()).fit()
    mu = poisson.predict(exog, offset=offset)
    alpha = max(float(np.sum(((y - mu) ** 2 - y) / mu**2) / max(len(y) - exog.shape[1], 1)), 0.01)
    return np.append(poisson.params, alpha)


def fit_spf(observed: list[int], features: list[dict[str, float]], offsets: list[float]) -> Spf:
    """NB2 regression: log mu = b0 + offset + sum(b_k x_k), alpha by maximum likelihood.

    The default optimiser can stall at alpha = 0 on overdispersed data, which would make EB
    trust the model completely; several optimisers start from a Poisson fit and the best
    likelihood wins.
    """
    names = tuple(sorted(features[0])) if features else ()
    y = np.array(observed, dtype=float)
    exog = np.column_stack(
        [np.ones(len(observed))] + [np.array([f[k] for f in features]) for k in names]
    )
    offset = np.array(offsets, dtype=float)
    model = sm.NegativeBinomial(y, exog, offset=offset, loglike_method="nb2")
    start = _start_params(y, exog, offset)
    best = None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # convergence chatter from the optimisers we discard
        for method in _FIT_METHODS:
            result = model.fit(start_params=start, method=method, maxiter=2000, disp=0)
            if np.all(np.isfinite(result.params)) and (best is None or result.llf > best.llf):
                best = result
    if best is None:
        raise ValueError("no optimiser converged")
    params = list(best.params)
    return Spf(
        intercept=float(params[0]),
        coefficients={k: float(v) for k, v in zip(names, params[1:-1], strict=True)},
        alpha=max(float(params[-1]), 0.0),
        n=len(observed),
        mean_observed=float(np.mean(y)) if observed else 0.0,
        log_likelihood=float(best.llf),
        features=names,
    )


def empirical_bayes(observed: int, predicted: float, alpha: float) -> tuple[float, float, float]:
    """(EB-expected collisions, excess over the prediction, weight on the prediction)."""
    weight = 1.0 / (1.0 + alpha * predicted)
    eb = weight * predicted + (1.0 - weight) * observed
    return eb, eb - predicted, weight
