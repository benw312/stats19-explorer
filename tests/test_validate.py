from stats19.validate import DEFAULT_THRESHOLDS


def test_default_thresholds_set_from_real_runs():
    # FU-007: runs 1-2 had 0 quarantine (after FU-008), 0 parse failures and
    # identical row counts; annual releases only add rows.
    assert DEFAULT_THRESHOLDS.max_quarantine_ratio == 0.001
    assert DEFAULT_THRESHOLDS.max_parse_failure_ratio == 0.0001
    assert DEFAULT_THRESHOLDS.min_row_ratio_vs_previous == 0.99
    assert DEFAULT_THRESHOLDS.first_year == 1979
