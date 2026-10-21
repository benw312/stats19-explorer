"""Out-of-sample check for the safety model (PLAN-008 §11, FU-038 #8).

Score every site on an earlier five years, pick the worst 2% by each ranking method, then
see how those sites did in the next five years, scored the same way. A good ranking picks
sites that stay worse than similar ones (large next-period excess), not sites that were
unlucky once (regression to the mean).

Methods, each picking the same number of sites per site type:
- ``eb_region``: Empirical Bayes excess ranked within peer group and region (the app).
- ``eb_national``: EB excess ranked nationally (before regional ranking, PLAN-008 §12).
- ``count``: raw collision count.
- ``rate``: observed / predicted (a raw rate against similar sites).

Run with ``stats19 safety-check``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import psycopg

from stats19.reference.safety_build import SAFETY_YEARS, UNIT_COLUMNS, score_period

TOP_SHARE = 0.02
STAYED_WORSE_SHARE = 0.20  # "still worse": in the worst 20% of its group next period
_COLUMNS = [c.strip() for c in UNIT_COLUMNS.split(",")]

Site = dict


@dataclass(frozen=True)
class MethodResult:
    unit_type: str
    method: str
    sites: int
    next_excess: float
    next_observed: int
    stayed_worse: float  # share of picked sites in their group's worst 20% next period
    region_share: dict[str, float]


def as_sites(rows: Iterable[tuple]) -> dict[tuple[str, str], Site]:
    """Unit rows from score_period, keyed by (unit_type, unit_id), as dicts."""
    out = {}
    for row in rows:
        site = dict(zip(_COLUMNS, row, strict=True))
        out[(site["unit_type"], site["unit_id"])] = site
    return out


def _regional_position(s: Site) -> float:
    return s["excess_rank"] / s["group_size"] if s["excess_rank"] and s["group_size"] else 2.0


METHODS: dict[str, Callable[[Site], tuple]] = {
    # sort keys: smallest first is "worst"
    "eb_region": lambda s: (_regional_position(s), -(s["excess"] or 0)),
    "eb_national": lambda s: (-(s["excess"] or 0),),
    "count": lambda s: (-s["observed"],),
    "rate": lambda s: (-(s["observed"] / s["predicted"]),),
}


def _stayed_worse(s: Site | None) -> bool:
    return s is not None and (s["excess"] or 0) > 0 and _regional_position(s) <= STAYED_WORSE_SHARE


def compare_periods(
    before: dict[tuple[str, str], Site],
    after: dict[tuple[str, str], Site],
    top_share: float = TOP_SHARE,
) -> list[MethodResult]:
    """For each site type and method: how the picked worst sites did next period."""
    results = []
    for unit_type in sorted({k[0] for k in before}):
        # modelled in the first period and present in the second
        pool = [s for k, s in before.items() if k[0] == unit_type and s["predicted"] and k in after]
        n = max(1, round(top_share * len(pool)))
        for method, key in METHODS.items():
            picked = sorted(pool, key=key)[:n]
            nxt = [after[(unit_type, s["unit_id"])] for s in picked]
            regions: dict[str, int] = {}
            for s in picked:
                regions[s["region"]] = regions.get(s["region"], 0) + 1
            results.append(
                MethodResult(
                    unit_type=unit_type,
                    method=method,
                    sites=n,
                    next_excess=sum(x["excess"] or 0 for x in nxt),
                    next_observed=sum(x["observed"] for x in nxt),
                    stayed_worse=sum(_stayed_worse(x) for x in nxt) / n,
                    region_share={r: c / n for r, c in sorted(regions.items())},
                )
            )
    return results


def run_check(
    conn: psycopg.Connection,
) -> tuple[tuple[int, int], tuple[int, int], list[MethodResult]]:
    latest = conn.execute("SELECT max(collision_year) FROM core.collision").fetchone()[0]
    after_years = (latest - SAFETY_YEARS + 1, latest)
    before_years = (after_years[0] - SAFETY_YEARS, after_years[0] - 1)
    before = as_sites(score_period(conn, *before_years)[0])
    after = as_sites(score_period(conn, *after_years)[0])
    return before_years, after_years, compare_periods(before, after)


def format_results(
    before_years: tuple[int, int], after_years: tuple[int, int], results: list[MethodResult]
) -> str:
    lines = [
        f"Ranked on {before_years[0]}-{before_years[1]}; "
        f"outcome in {after_years[0]}-{after_years[1]} (worst {TOP_SHARE:.0%} picked)",
        "",
        "| Sites | Method | Picked | Next excess | Next collisions | Still worst 20% | Regions |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        regions = ", ".join(f"{k} {v:.0%}" for k, v in r.region_share.items())
        lines.append(
            f"| {r.unit_type} | {r.method} | {r.sites:,} | {r.next_excess:,.0f} | "
            f"{r.next_observed:,} | {r.stayed_worse:.0%} | {regions} |"
        )
    return "\n".join(lines)
