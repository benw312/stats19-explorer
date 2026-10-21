"""Does "low sun ahead" pick out glare? A check of the sun bands (PLAN-012 C1).

The police "dazzling sun" factor isn't in the open data, so the bands can't be checked
collision by collision. Instead this compares like with like:

- **Ahead against behind.** Traffic runs both ways at the same times, so with no glare
  the sun is low and ahead about as often as it's low and behind. More "ahead" than
  "behind" is the glare signal.
- **Fine weather against rain.** Rain means cloud, so no direct sun. The ratio should
  be about 1 there, and the fine-weather ratio over the rain ratio isolates glare from
  any directional bias in traffic or recording.

Split by where the heading came from: the link's bearing is good to a few degrees, the
compass to ±22.5°, which blurs a ±30° test. Run with ``stats19 context-check``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import psycopg

Z95 = 1.959964
FINE = (1, 4)  # STATS19 weather_conditions: fine, without or with high winds
RAIN = (2, 5)  # raining, without or with high winds


@dataclass(frozen=True)
class Ratio:
    source: str
    fine_ahead: int
    fine_behind: int
    rain_ahead: int
    rain_behind: int

    @property
    def fine(self) -> float:
        return self.fine_ahead / self.fine_behind

    @property
    def rain(self) -> float:
        return self.rain_ahead / self.rain_behind

    def glare(self) -> tuple[float, float, float]:
        """Fine ratio ÷ rain ratio with its 95% CI (an odds ratio, Woolf's method)."""
        cells = (self.fine_ahead, self.fine_behind, self.rain_ahead, self.rain_behind)
        if min(cells) == 0:
            return math.nan, math.nan, math.nan
        log_or = math.log(self.fine / self.rain)
        se = math.sqrt(sum(1 / n for n in cells))
        return math.exp(log_or), math.exp(log_or - Z95 * se), math.exp(log_or + Z95 * se)


_QUERY = """
SELECT v.heading_source AS source,
       count(*) FILTER (WHERE fine AND v.sun_band = 'low_ahead') AS fine_ahead,
       count(*) FILTER (WHERE fine AND v.sun_band = 'low_behind') AS fine_behind,
       count(*) FILTER (WHERE rain AND v.sun_band = 'low_ahead') AS rain_ahead,
       count(*) FILTER (WHERE rain AND v.sun_band = 'low_behind') AS rain_behind
FROM geo.vehicle_context v
JOIN LATERAL (
    SELECT c.weather_conditions = ANY(%(fine)s) AS fine,
           c.weather_conditions = ANY(%(rain)s) AS rain
    FROM core.collision c
    WHERE c.collision_index = v.collision_index AND c.collision_year >= %(since)s) c ON true
WHERE v.sun_band IN ('low_ahead', 'low_behind')
GROUP BY 1 ORDER BY 1
"""


def run_check(conn: psycopg.Connection, since: int) -> list[Ratio]:
    rows = conn.execute(_QUERY, {"fine": list(FINE), "rain": list(RAIN), "since": since}).fetchall()
    return [Ratio(*r) for r in rows]


def format_results(since: int, ratios: list[Ratio]) -> str:
    lines = [
        f"Vehicles in a collision with a low sun (0-15 degrees up), {since} on: sun within 30 "
        "degrees of the heading (ahead) against within 30 degrees of the reverse (behind)",
        "",
        "| Heading from | Fine: ahead / behind | Ratio | Rain: ahead / behind | Ratio | "
        "Fine / rain (95% CI) |",
        "|---|---|---|---|---|---|",
    ]
    for r in ratios:
        g, lo, hi = r.glare()
        lines.append(
            f"| {r.source} | {r.fine_ahead:,} / {r.fine_behind:,} | {r.fine:.3f} | "
            f"{r.rain_ahead:,} / {r.rain_behind:,} | {r.rain:.3f} | "
            f"{g:.3f} ({lo:.3f}-{hi:.3f}) |"
        )
    lines += [
        "",
        "Fine / rain above 1, with its CI clear of 1, is the glare signal: low sun ahead is "
        "over-represented when the sun can be seen, and not otherwise.",
    ]
    return "\n".join(lines)
