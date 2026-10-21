"""Cluster sites by greedy circles (PLAN-005 §2).

Every collision is a candidate circle centre, with the cluster radius for its own
urban/rural setting. The best-scoring circle becomes a site and its collisions are
used up; repeat while a circle still qualifies. Sites are therefore never wider than
two radii (no corridor chaining), and a run is deterministic.
"""

from __future__ import annotations

import heapq
import math
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

KSI_WEIGHT = 3  # KSI-weighted score: slight = 1, fatal or serious = 3

ScoreMethod = Literal["ksi_weighted", "count", "value"]


class HotspotParams(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    radius_urban_m: int = Field(default=50, ge=10, le=500)
    radius_rural_m: int = Field(default=100, ge=10, le=1000)
    min_collisions: int = Field(default=5, ge=1, le=500)
    min_ksi: int = Field(default=2, ge=1, le=500)
    score: ScoreMethod = "ksi_weighted"
    max_sites: int = Field(default=50, ge=1, le=200)


@dataclass(frozen=True, slots=True)
class Point:
    id: str
    x: float  # British National Grid, metres
    y: float
    severity: int  # 1 fatal, 2 serious, 3 slight
    rural: bool
    year: int
    value: float = 0.0  # value of prevention for this collision's severity
    # DfT's adjusted probability that it's KSI (fatal = 1): forces record serious injuries
    # differently, so the score uses this when given; the KSI count stays as recorded
    p_ksi: float | None = None


@dataclass(frozen=True)
class Site:
    rank: int
    centre: Point  # the collision the circle is centred on
    radius_m: int
    members: tuple[Point, ...]
    score: float

    @property
    def collisions(self) -> int:
        return len(self.members)

    @property
    def fatal(self) -> int:
        return sum(p.severity == 1 for p in self.members)

    @property
    def serious(self) -> int:
        return sum(p.severity == 2 for p in self.members)

    @property
    def slight(self) -> int:
        return sum(p.severity == 3 for p in self.members)

    @property
    def ksi(self) -> int:
        return self.fatal + self.serious

    @property
    def cx(self) -> float:
        return sum(p.x for p in self.members) / len(self.members)

    @property
    def cy(self) -> float:
        return sum(p.y for p in self.members) / len(self.members)


def _is_ksi(p: Point) -> bool:
    return p.severity in (1, 2)


def _weight(method: ScoreMethod) -> Callable[[Point], float]:
    if method == "count":
        return lambda p: 1.0
    if method == "value":
        return lambda p: p.value
    return lambda p: 1 + (KSI_WEIGHT - 1) * _ksi_share(p)


def _ksi_share(p: Point) -> float:
    if p.p_ksi is not None:
        return p.p_ksi
    return 1.0 if _is_ksi(p) else 0.0


def _neighbours(points: Sequence[Point], radius: Callable[[Point], int]) -> list[list[int]]:
    """For each point, the indexes of points within its own radius (itself included)."""
    cell = max(radius(p) for p in points)
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, p in enumerate(points):
        grid[(math.floor(p.x / cell), math.floor(p.y / cell))].append(i)
    out = []
    for p in points:
        gx, gy, r2 = math.floor(p.x / cell), math.floor(p.y / cell), radius(p) ** 2
        near = [
            j
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            for j in grid.get((gx + dx, gy + dy), ())
            if (points[j].x - p.x) ** 2 + (points[j].y - p.y) ** 2 <= r2
        ]
        out.append(sorted(near))
    return out


def find_sites(points: Sequence[Point], params: HotspotParams) -> list[Site]:
    """Ranked cluster sites; no collision belongs to more than one site."""
    if not points:
        return []

    def radius(p: Point) -> int:
        return params.radius_rural_m if p.rural else params.radius_urban_m

    weight = _weight(params.score)
    members = _neighbours(points, radius)
    used = [False] * len(points)

    def key(i: int) -> tuple[float, int, int]:
        live = [points[j] for j in members[i] if not used[j]]
        return (sum(weight(p) for p in live), sum(_is_ksi(p) for p in live), len(live))

    def qualifies(k: tuple[float, int, int]) -> bool:
        return k[2] >= params.min_collisions or k[1] >= params.min_ksi

    # Lazy greedy: scores only fall as collisions are used, so a popped entry whose
    # recomputed key is unchanged is the true best.
    heap = []
    for i in range(len(points)):
        k = key(i)
        if qualifies(k):
            heap.append((-k[0], -k[1], -k[2], points[i].id, i))
    heapq.heapify(heap)

    sites: list[Site] = []
    while heap and len(sites) < params.max_sites:
        neg_score, neg_ksi, neg_n, pid, i = heapq.heappop(heap)
        if used[i]:
            continue  # the centre already belongs to a site
        k = key(i)
        if not qualifies(k):
            continue  # can only shrink further
        if k != (-neg_score, -neg_ksi, -neg_n):
            heapq.heappush(heap, (-k[0], -k[1], -k[2], pid, i))
            continue
        live = tuple(points[j] for j in members[i] if not used[j])
        for j in members[i]:
            used[j] = True
        sites.append(
            Site(
                rank=len(sites) + 1,
                centre=points[i],
                radius_m=radius(points[i]),
                members=live,
                score=k[0],
            )
        )
    return sites


def binomial_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p): one-sided exact test for over-representation."""
    if k <= 0:
        return 1.0
    if k > n or p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    log_p, log_q = math.log(p), math.log1p(-p)
    total = 0.0
    for x in range(k, n + 1):
        log_c = math.lgamma(n + 1) - math.lgamma(x + 1) - math.lgamma(n - x + 1)
        total += math.exp(log_c + x * log_p + (n - x) * log_q)
    return min(total, 1.0)
