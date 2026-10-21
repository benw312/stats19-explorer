"""/api/schemes/{id}/evaluation (PLAN-011 §3, V5 S3): counting, method choice and result."""

from datetime import date

import pytest

from stats19 import evaluation as ev
from stats19.api import scheme_evaluation, writes
from stats19.api.limits import RateLimit
from stats19.api.scheme_periods import Period

from .test_schemes import AROUND_1979A, SAME_SITE, scheme

# copies of 1979A, in AROUND_1979A or 50 km east (the comparison area)
INSIDE, OUTSIDE = 0.0, 50_000.0
BEFORE = Period(date(2018, 1, 1), date(2020, 12, 31))
AFTER = Period(date(2021, 7, 1), date(2024, 6, 30))


@pytest.fixture
def ev_api(api, db_conn, monkeypatch):
    monkeypatch.setattr(writes, "LIMIT", RateLimit(1000, 60))
    scheme_evaluation.clear_cache()
    yield api
    scheme_evaluation.clear_cache()


def add_collisions(conn, east_m: float, when: date, n: int, *, at_junction: bool = False) -> None:
    """n copies of the fixture's 1979A, moved east_m metres east, on a date and recorded at a
    junction or not."""
    conn.execute(
        "CREATE TEMP TABLE c AS SELECT * FROM core.collision WHERE collision_index = '1979A'"
    )
    conn.execute("UPDATE c SET geom_bng = ST_Translate(geom_bng, %s, 0)", (east_m,))
    conn.execute(
        """UPDATE c SET collision_date = %s, collision_year = %s, road_type = %s,
                        junction_detail = 0, junction_detail_historic = -1,
                        junction_control = -1, collision_severity = 3, first_road_class = 3""",
        (when, when.year, 1 if at_junction else 6),
    )
    for i in range(n):
        conn.execute(
            "UPDATE c SET collision_index = %s", (f"T{east_m:.0f}-{when}-{at_junction:d}-{i}",)
        )
        conn.execute("INSERT INTO core.collision SELECT * FROM c")
    conn.execute("DROP TABLE c")
    conn.commit()


def save(api, **overrides) -> str:
    body = scheme(
        **{
            "geometry": AROUND_1979A,
            "site_type": "area",
            "site_ref": None,
            "works_start": "2021-01-01",
            "works_end": "2021-06-30",
        }
        | overrides
    )
    r = api.post("/api/schemes", json=body, headers=SAME_SITE)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def evaluation(api, scheme_id: str) -> dict:
    r = api.get(f"/api/schemes/{scheme_id}/evaluation")
    assert r.status_code == 200, r.text
    return r.json()["data"]


def history(conn, *, inside=(6, 2), outside=(100, 100), at_junction=False) -> None:
    """Collisions before (2019) and after (2022) at the scheme and in the comparison area,
    with data loaded to the end of 2024 so the after period is complete."""
    add_collisions(conn, INSIDE, date(2019, 5, 1), inside[0], at_junction=at_junction)
    add_collisions(conn, INSIDE, date(2022, 5, 1), inside[1], at_junction=at_junction)
    add_collisions(conn, OUTSIDE, date(2019, 5, 1), outside[0], at_junction=at_junction)
    add_collisions(conn, OUTSIDE, date(2022, 5, 1), outside[1], at_junction=at_junction)
    add_collisions(conn, OUTSIDE, date(2024, 12, 1), 1, at_junction=not at_junction)


@pytest.mark.integration
def test_an_area_scheme_is_compared_with_the_rest_of_great_britain(ev_api, db_conn):
    history(db_conn, inside=(20, 4))
    scheme_id = save(ev_api)

    d = evaluation(ev_api, scheme_id)

    assert (d["stage"], d["method"], d["message"]) == ("complete", "comparison", None)
    assert d["before"] == {"start": "2018-01-01", "end": "2020-12-31"}
    assert d["after"] == {"start": "2021-07-01", "end": "2024-06-30"}
    assert d["counts"] == {"before": 20, "after": 4, "ksi_before": 0, "ksi_after": 0}
    # no boundaries in the fixture: the rest of GB, which had 100 before and 100 after
    assert d["comparison"]["name"] == "the rest of Great Britain"
    assert (d["comparison"]["before"], d["comparison"]["after"]) == (100, 100)
    want = ev.comparison_group(20, 4, 100, 100)
    assert d["result"]["theta"] == pytest.approx(want.theta, abs=1e-4)
    assert d["result"]["upper"] == pytest.approx(want.upper, abs=1e-4)
    assert d["verdict"] == "fewer"
    assert "regression to the mean" in d["headline"]
    # 20 expected after, 4 seen: 16 saved over 3 years
    assert d["result"]["saved_a_year"] == pytest.approx(16 / ev.years_of(AFTER), abs=0.01)
    v = d["value"]
    assert v["expected_saved_a_year"] == pytest.approx(0.72)  # 2.4 a year x 30%
    assert v["expected_fyrr_pct"] == pytest.approx(34.6)  # 0.72 x £120k / £250k
    assert v["achieved_fyrr_pct"] == pytest.approx(
        ev.fyrr_pct(16 / ev.years_of(AFTER), 120_000, 250_000), abs=0.1
    )


SAFETY_TABLES = """
DROP TABLE IF EXISTS geo.safety_unit, geo.safety_model, geo.safety_calibration;
CREATE TABLE geo.safety_unit (unit_type text, unit_id text, peer_group text,
                              predicted double precision);
CREATE TABLE geo.safety_model (unit_type text, peer_group text, alpha double precision);
CREATE TABLE geo.safety_calibration (unit_type text, peer_group text, year integer,
                                     factor double precision);
"""


def model(conn, *, predicted: float, alpha: float, factors: dict[int, float]) -> None:
    for statement in SAFETY_TABLES.split(";")[:-1]:
        conn.execute(statement)
    conn.execute(
        "INSERT INTO geo.safety_unit VALUES ('junction', 'J9', 'signals/urban', %s)", (predicted,)
    )
    conn.execute("INSERT INTO geo.safety_model VALUES ('junction', 'signals/urban', %s)", (alpha,))
    for year, factor in factors.items():
        conn.execute(
            "INSERT INTO geo.safety_calibration VALUES ('junction', 'signals/urban', %s, %s)",
            (year, factor),
        )
    conn.commit()


@pytest.mark.integration
def test_a_junction_with_a_model_gets_empirical_bayes_with_the_trend(ev_api, db_conn):
    history(db_conn, inside=(9, 2), at_junction=True)
    # 10 predicted over the model's 5 years: 2 a year, with a falling trend
    factors = {2018: 1.0, 2019: 1.0, 2020: 1.0, 2021: 0.9, 2022: 0.9, 2023: 0.8}
    model(db_conn, predicted=10.0, alpha=0.3, factors=factors)
    scheme_id = save(ev_api, site_type="junction", site_ref="J9")

    d = evaluation(ev_api, scheme_id)

    assert d["method"] == "eb" and "signals/urban" in d["method_note"]
    assert d["counts"]["before"] == 9 and d["counts"]["after"] == 2
    spf = dict.fromkeys(range(2018, 2025), 2.0)
    mu_b = ev.period_prediction(spf, factors, BEFORE)
    mu_a = ev.period_prediction(spf, factors, AFTER)  # 2024 borrows 2023's 0.8
    want = ev.eb_before_after(9, 2, mu_b, mu_a, 0.3)
    assert d["eb"]["mu_before"] == pytest.approx(mu_b, abs=1e-3)
    assert d["eb"]["mu_after"] == pytest.approx(mu_a, abs=1e-3)
    assert d["result"]["theta"] == pytest.approx(want.theta, abs=1e-4)
    assert d["result"]["lower"] == pytest.approx(want.lower, abs=1e-4)
    assert d["headline"] == ev.describe(want, 36)
    assert d["comparison"] is None


@pytest.mark.integration
def test_a_junction_scheme_counts_only_junction_collisions(ev_api, db_conn):
    history(db_conn, inside=(5, 1), at_junction=False)
    add_collisions(db_conn, INSIDE, date(2019, 6, 1), 3, at_junction=True)
    add_collisions(db_conn, OUTSIDE, date(2019, 6, 1), 50, at_junction=True)
    add_collisions(db_conn, OUTSIDE, date(2022, 6, 1), 50, at_junction=True)

    junction = evaluation(ev_api, save(ev_api, site_type="junction", site_ref="J0"))
    area = evaluation(ev_api, save(ev_api, name="Same place, as an area"))

    # no model for J0: the comparison group, of junction collisions only
    assert junction["method"] == "comparison" and "no safety model" in junction["method_note"]
    assert (junction["counts"]["before"], junction["counts"]["after"]) == (3, 0)
    assert junction["comparison"]["before"] == 50
    assert (area["counts"]["before"], area["counts"]["after"]) == (8, 1)


@pytest.mark.integration
@pytest.mark.parametrize(
    "dates, message",
    [
        ({"works_start": None, "works_end": None}, "Add the works dates"),
        ({"works_start": "2024-01-01", "works_end": None}, "once the works have an end date"),
        (
            {"works_start": "2025-01-01", "works_end": "2025-03-31"},
            "DfT publishes 2025's collisions in September 2026",
        ),
    ],
)
def test_no_result_until_there_is_after_data(ev_api, db_conn, dates, message):
    history(db_conn)
    d = evaluation(ev_api, save(ev_api, **dates))
    assert d["result"] is None and message in d["message"]


@pytest.mark.integration
def test_a_short_after_period_is_too_early_to_tell(ev_api, db_conn):
    history(db_conn)
    d = evaluation(ev_api, save(ev_api, works_start="2024-01-01", works_end="2024-03-31"))
    assert (d["after_months"], d["verdict"]) == (9, "too_early")
    assert d["headline"].startswith("Too early to tell: 9 months")


@pytest.mark.integration
def test_no_collisions_at_the_scheme_gives_a_reason_not_a_result(ev_api, db_conn):
    history(db_conn, inside=(0, 0))
    d = evaluation(ev_api, save(ev_api))
    assert d["result"] is None and "No collisions at the scheme" in d["message"]


@pytest.mark.integration
def test_results_are_cached_until_the_scheme_changes(ev_api, db_conn):
    history(db_conn)
    scheme_id = save(ev_api)
    first = evaluation(ev_api, scheme_id)
    add_collisions(db_conn, INSIDE, date(2022, 8, 1), 3)

    assert evaluation(ev_api, scheme_id)["counts"] == first["counts"]  # same load, same version
    body = scheme(
        geometry=AROUND_1979A,
        site_type="area",
        site_ref=None,
        works_start="2021-01-01",
        works_end="2021-06-30",
        version=1,
    )
    assert ev_api.put(f"/api/schemes/{scheme_id}", json=body, headers=SAME_SITE).status_code == 200
    assert evaluation(ev_api, scheme_id)["counts"]["after"] == 5


@pytest.mark.integration
def test_unknown_scheme_is_not_found(ev_api):
    r = ev_api.get("/api/schemes/00000000-0000-0000-0000-00000000abcd/evaluation")
    assert r.status_code == 404
