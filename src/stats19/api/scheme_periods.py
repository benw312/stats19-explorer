"""A scheme's before and after periods and how much after-data has arrived (PLAN-011 §3).

The works are left out of both periods: "before" is the ``before_years`` up to the day the
works started, and "after" is the ``after_years`` from the day after they ended. DfT
publishes a whole year at a time, so the data runs to 31 December of the latest loaded year.

Pure functions, so the rules are unit-tested without a database; S3's evaluation uses the
same periods.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

Stage = Literal["undated", "in_works", "monitoring", "complete"]


@dataclass(frozen=True)
class Period:
    start: date
    end: date  # inclusive


@dataclass(frozen=True)
class Periods:
    before: Period | None
    after: Period | None
    stage: Stage
    #: Whole months of after-data loaded, and how many the after period needs.
    after_months: int
    after_months_wanted: int
    data_end: date | None


def add_years(d: date, years: int) -> date:
    """The same day ``years`` later (or earlier); 29 February becomes 28 February."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def months_between(start: date, end: date) -> int:
    """Whole months from ``start`` to ``end`` inclusive (1 Jan to 31 Mar is 3)."""
    if end < start:
        return 0
    day_after = end + timedelta(days=1)
    months = (day_after.year - start.year) * 12 + day_after.month - start.month
    if day_after.day < start.day:
        months -= 1
    return max(0, months)


def scheme_periods(
    works_start: date | None,
    works_end: date | None,
    before_years: int,
    after_years: int,
    last_year: int | None,
) -> Periods:
    """The before and after periods, and the stage given data up to ``last_year``.

    The before period needs a start date (the end date stands in when only that is known).
    The after period needs the end date: until the works are recorded as finished, the
    scheme is "in works" however long ago they started.
    """
    wanted = after_years * 12
    data_end = date(last_year, 12, 31) if last_year is not None else None
    start = works_start or works_end
    before = Period(add_years(start, -before_years), start - timedelta(days=1)) if start else None
    if works_end is None:
        stage: Stage = "undated" if before is None else "in_works"
        return Periods(before, None, stage, 0, wanted, data_end)
    after_start = works_end + timedelta(days=1)
    after = Period(after_start, add_years(works_end, after_years))
    have = 0 if data_end is None else min(wanted, months_between(after_start, data_end))
    stage = "complete" if have >= wanted else "monitoring"
    return Periods(before, after, stage, have, wanted, data_end)


def chart_years(periods: Periods, first_year: int, last_year: int, span: int = 10) -> range:
    """The years to chart: the before period to the end of the after period, within the
    loaded data. Without dates, the latest ``span`` years."""
    if periods.before is None:
        return range(max(first_year, last_year - span + 1), last_year + 1)
    end = periods.after.end.year if periods.after else periods.before.end.year + 1
    lo = max(first_year, periods.before.start.year)
    hi = min(last_year, max(end, lo))
    return range(lo, hi + 1)
