"""A scheme's before and after periods (PLAN-011 §3): pure rules, no database."""

from datetime import date

from stats19.api.scheme_periods import (
    Period,
    add_years,
    chart_years,
    months_between,
    scheme_periods,
)


def test_add_years_keeps_the_day_and_moves_29_february_to_the_28th():
    assert add_years(date(2021, 3, 1), -3) == date(2018, 3, 1)
    assert add_years(date(2024, 2, 29), 1) == date(2025, 2, 28)


def test_months_between_counts_whole_months_inclusive():
    assert months_between(date(2022, 1, 1), date(2022, 3, 31)) == 3
    assert months_between(date(2021, 7, 1), date(2024, 12, 31)) == 42
    assert months_between(date(2021, 7, 15), date(2021, 8, 13)) == 0
    assert months_between(date(2021, 7, 15), date(2021, 8, 14)) == 1
    assert months_between(date(2023, 1, 1), date(2022, 12, 31)) == 0


def test_periods_leave_out_the_works():
    p = scheme_periods(date(2021, 3, 1), date(2021, 6, 30), 3, 3, last_year=2024)
    assert p.before == Period(date(2018, 3, 1), date(2021, 2, 28))
    assert p.after == Period(date(2021, 7, 1), date(2024, 6, 30))


def test_monitoring_counts_the_months_of_after_data_loaded():
    p = scheme_periods(date(2023, 3, 1), date(2023, 6, 30), 3, 3, last_year=2024)
    assert p.stage == "monitoring"
    assert (p.after_months, p.after_months_wanted) == (18, 36)
    assert p.data_end == date(2024, 12, 31)


def test_complete_once_the_whole_after_period_is_loaded():
    p = scheme_periods(date(2020, 3, 1), date(2020, 6, 30), 3, 3, last_year=2024)
    assert p.stage == "complete"
    assert p.after_months == 36


def test_after_period_not_yet_reached_is_monitoring_with_no_months():
    p = scheme_periods(date(2025, 3, 1), date(2025, 6, 30), 3, 2, last_year=2024)
    assert (p.stage, p.after_months, p.after_months_wanted) == ("monitoring", 0, 24)


def test_without_an_end_date_the_scheme_is_in_works():
    p = scheme_periods(date(2024, 3, 1), None, 3, 3, last_year=2024)
    assert p.stage == "in_works"
    assert p.before == Period(date(2021, 3, 1), date(2024, 2, 29))
    assert p.after is None


def test_end_date_alone_stands_in_for_the_start():
    p = scheme_periods(None, date(2022, 9, 30), 2, 3, last_year=2024)
    assert p.before == Period(date(2020, 9, 30), date(2022, 9, 29))
    assert p.after == Period(date(2022, 10, 1), date(2025, 9, 30))


def test_no_dates_is_undated():
    p = scheme_periods(None, None, 3, 3, last_year=2024)
    assert (p.stage, p.before, p.after) == ("undated", None, None)


def test_no_data_loaded_means_no_after_months():
    p = scheme_periods(date(2020, 1, 1), date(2020, 2, 1), 3, 3, last_year=None)
    assert (p.stage, p.after_months, p.data_end) == ("monitoring", 0, None)


def test_chart_years_span_both_periods_within_the_data():
    p = scheme_periods(date(2021, 3, 1), date(2021, 6, 30), 3, 3, last_year=2023)
    assert chart_years(p, 1979, 2023) == range(2018, 2024)


def test_chart_years_without_dates_are_the_latest_ten():
    p = scheme_periods(None, None, 3, 3, last_year=2024)
    assert chart_years(p, 1979, 2024) == range(2015, 2025)
    assert chart_years(p, 2020, 2024) == range(2020, 2025)


def test_chart_years_in_works_show_the_before_period_and_the_works_year():
    p = scheme_periods(date(2022, 5, 1), None, 3, 3, last_year=2024)
    assert chart_years(p, 1979, 2024) == range(2019, 2024)


def test_chart_years_for_future_works_stop_at_the_data():
    p = scheme_periods(date(2026, 5, 1), date(2026, 8, 1), 3, 3, last_year=2024)
    assert chart_years(p, 1979, 2024) == range(2023, 2025)
