"""Yearly calibration factors for the safety models (PLAN-011 §3, V5 S3)."""

import pytest

from stats19.reference.safety_calibration import calibration_rows

YEARS = range(2021, 2024)


def test_factor_is_the_groups_observed_over_its_yearly_prediction():
    # two junctions in one group, predicted 10 and 5 over a 5-year model: 3 a year together
    units = [("junction", "a", "signals/urban", 10.0), ("junction", "b", "signals/urban", 5.0)]
    counts = {("junction", "a"): {2021: 2, 2022: 3}, ("junction", "b"): {2021: 1, 2023: 6}}

    rows = calibration_rows(units, counts, YEARS, model_years=5)

    assert rows == [
        ("junction", "signals/urban", 2021, 3, pytest.approx(3.0), pytest.approx(1.0)),
        ("junction", "signals/urban", 2022, 3, pytest.approx(3.0), pytest.approx(1.0)),
        ("junction", "signals/urban", 2023, 6, pytest.approx(3.0), pytest.approx(2.0)),
    ]


def test_groups_and_unit_types_are_kept_apart():
    units = [("junction", "1", "g", 5.0), ("link", "1", "g", 10.0)]
    counts = {("junction", "1"): {2021: 1}, ("link", "1"): {2021: 4}}

    rows = calibration_rows(units, counts, range(2021, 2022), model_years=5)

    assert [(r[0], r[3], r[5]) for r in rows] == [
        ("junction", 1, pytest.approx(1.0)),
        ("link", 4, pytest.approx(2.0)),
    ]


def test_sites_without_a_model_and_years_outside_the_range_are_left_out():
    units = [("junction", "a", "g", 5.0), ("junction", "b", "g", None)]
    # b has no prediction (its group wasn't fitted), so its collisions don't count either
    counts = {("junction", "a"): {2020: 9, 2021: 1}, ("junction", "b"): {2021: 50}}

    rows = calibration_rows(units, counts, range(2021, 2022), model_years=5)

    assert rows == [("junction", "g", 2021, 1, pytest.approx(1.0), pytest.approx(1.0))]


def test_a_year_with_no_collisions_has_a_factor_of_zero():
    rows = calibration_rows([("link", "x", "g", 5.0)], {}, range(2021, 2022), model_years=5)
    assert rows == [("link", "g", 2021, 0, pytest.approx(1.0), 0.0)]
