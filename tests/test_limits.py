"""Caps on expensive work running at once (PLAN-006 C5)."""

import pytest

from stats19.api.envelope import ApiError
from stats19.api.limits import Limiter


def test_a_third_job_is_turned_away_while_two_run_and_admitted_after():
    pdf = Limiter("pdf", 2)

    with pdf.slot(), pdf.slot():
        with pytest.raises(ApiError) as busy, pdf.slot():
            pass
        assert busy.value.status == 503 and busy.value.code == "busy"

    with pdf.slot():  # slots come back when a job finishes, even after an error
        pass


def test_a_failing_job_gives_its_slot_back():
    one = Limiter("x", 1)
    with pytest.raises(RuntimeError), one.slot():
        raise RuntimeError("render failed")

    with one.slot():
        pass
