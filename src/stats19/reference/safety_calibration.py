"""Yearly calibration factors for the safety models (PLAN-011 §3, V5 S3).

Each peer group's model is fitted on the pooled latest ``SAFETY_YEARS`` years, so it knows
nothing of the year-to-year trend: fewer collisions nationally, a change in police
recording, a wet winter. A scheme's before and after periods fall in different years, so
the EB evaluation scales the model by each year's factor: the group's observed collisions
that year ÷ its predicted collisions for a year. Over the fitting years the factors
average about 1, because an NB model's predictions sum to the observed total.

Counted over the years the collision matches cover (the last ``COLLISION_YEARS``), with
the same rules as the models: a junction counts its junction collisions; a link counts the
collisions matched to its stretch that aren't junction collisions.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

import psycopg

DDL = """CREATE TABLE geo.safety_calibration__new (
    unit_type text NOT NULL, peer_group text NOT NULL, year integer NOT NULL,
    observed integer NOT NULL, predicted double precision NOT NULL,
    factor double precision NOT NULL)"""
COLUMNS = "unit_type, peer_group, year, observed, predicted, factor"
INDEXES = ["ALTER TABLE geo.safety_calibration ADD PRIMARY KEY (unit_type, peer_group, year)"]

_JUNCTION_YEARS = """
SELECT 'junction', jc.junction_id, c.collision_year, count(*)
FROM geo.junction_collision jc JOIN core.collision c USING (collision_index)
WHERE c.collision_year BETWEEN %(y0)s AND %(y1)s
GROUP BY 2, 3
"""

_LINK_YEARS = """
SELECT 'link', t.count_point_id::text, c.collision_year, count(*)
FROM geo.traffic_link t
JOIN geo.collision_link m
  ON m.link_id = t.link_id AND m.frac >= t.frac_from AND (m.frac < t.frac_to OR t.frac_to >= 1)
JOIN core.collision c ON c.collision_index = m.collision_index
WHERE t.method = 'major' AND c.collision_year BETWEEN %(y0)s AND %(y1)s
  AND NOT EXISTS (SELECT 1 FROM geo.junction_collision jc
                  WHERE jc.collision_index = m.collision_index)
GROUP BY 2, 3
"""

Key = tuple[str, str]  # (unit_type, unit_id)


def yearly_counts(conn: psycopg.Connection, y0: int, y1: int) -> dict[Key, dict[int, int]]:
    """Each site's collisions per year, y0-y1, by the models' counting rules."""
    out: dict[Key, dict[int, int]] = defaultdict(dict)
    for query in (_JUNCTION_YEARS, _LINK_YEARS):
        for unit_type, unit_id, year, n in conn.execute(query, {"y0": y0, "y1": y1}):
            out[(unit_type, unit_id)][year] = n
    return out


def calibration_rows(
    units: Iterable[tuple[str, str, str, float | None]],
    counts: Mapping[Key, Mapping[int, int]],
    years: range,
    model_years: int,
) -> list[tuple[str, str, int, int, float, float]]:
    """(unit_type, peer_group, year, observed, predicted, factor) per scored group and year.

    ``units`` are (unit_type, unit_id, peer_group, predicted over ``model_years``); sites
    without a prediction (their group has no model) are left out, so a group's observed
    and predicted cover the same sites.
    """
    predicted: dict[Key, float] = defaultdict(float)
    observed: dict[Key, dict[int, int]] = defaultdict(lambda: dict.fromkeys(years, 0))
    for unit_type, unit_id, group, pred in units:
        if pred is None:
            continue
        key = (unit_type, group)
        predicted[key] += pred / model_years
        for year, n in counts.get((unit_type, unit_id), {}).items():
            if year in years:
                observed[key][year] += n
    rows = []
    for (unit_type, group), per_year in sorted(predicted.items()):
        if per_year <= 0:
            continue
        for year in years:
            n = observed[(unit_type, group)][year]
            rows.append((unit_type, group, year, n, per_year, n / per_year))
    return rows
