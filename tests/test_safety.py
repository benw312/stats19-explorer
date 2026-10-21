"""Safety performance functions and Empirical Bayes (PLAN-008 T4)."""

import math
import random

import pytest

from stats19.reference.safety import (
    URBAN_JUNCTIONS_500M,
    assign_groups,
    empirical_bayes,
    fit_spf,
    is_urban,
    junction_family,
    link_family,
    typical_minor_flows,
)


def test_urban_threshold():
    assert is_urban(URBAN_JUNCTIONS_500M)
    assert not is_urban(URBAN_JUNCTIONS_500M - 1)


@pytest.mark.parametrize(
    ("category", "dual", "urban", "expected"),
    [
        ("TM", True, False, ("motorway", "dual", "rural")),
        ("PM", True, True, ("motorway", "dual", "urban")),
        ("TA", False, False, ("trunk_a", "single", "rural")),
        ("PA", True, True, ("principal_a", "dual", "urban")),
    ],
)
def test_link_family(category, dual, urban, expected):
    assert link_family(category, dual, urban) == expected


@pytest.mark.parametrize(
    ("kind", "signalised", "urban", "expected"),
    [
        ("roundabout", True, True, ("roundabout", "urban")),
        ("mini_roundabout", False, True, ("mini_roundabout", "urban")),
        ("t_junction", True, False, ("signals", "rural")),
        ("t_junction", False, False, ("priority_t", "rural")),
        ("crossroads", False, True, ("priority_cross", "urban")),
        ("multi_arm", None, True, ("priority_cross", "urban")),
    ],
)
def test_junction_family(kind, signalised, urban, expected):
    assert junction_family(kind, signalised, urban) == expected


def test_small_groups_drop_their_last_split():
    families = (
        [("pa", "dual", "urban")] * 3
        + [("pa", "single", "urban")] * 150
        + [("pa", "dual", "rural")] * 2
    )

    got = assign_groups(families, min_size=100)

    assert got[0] == "pa"  # pa/dual/urban (3) -> pa/dual (5) -> pa
    assert got[3] == "pa/single/urban"
    assert got[-1] == "pa"


def test_empirical_bayes_pulls_towards_the_prediction():
    eb, excess, w = empirical_bayes(observed=10, predicted=4.0, alpha=0.5)

    assert w == pytest.approx(1 / (1 + 0.5 * 4.0))
    assert eb == pytest.approx(w * 4.0 + (1 - w) * 10)
    assert excess == pytest.approx(eb - 4.0)
    assert 4.0 < eb < 10


def test_no_overdispersion_trusts_the_model():
    assert empirical_bayes(observed=10, predicted=4.0, alpha=0.0)[0] == pytest.approx(4.0)


def test_fit_recovers_the_flow_exponent():
    rng = random.Random(7)
    rows = []
    for _ in range(3000):
        aadf = math.exp(rng.uniform(math.log(2000), math.log(60000)))
        length = rng.uniform(0.3, 5.0)
        mu = math.exp(-9.0) * length * aadf**0.8
        # negative binomial draw (alpha 0.3) via a gamma-mixed Poisson
        lam = rng.gammavariate(1 / 0.3, mu * 0.3)
        rows.append((_poisson(rng, lam), {"log_flow": math.log(aadf)}, math.log(length)))

    spf = fit_spf([r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows])

    assert spf.coefficients["log_flow"] == pytest.approx(0.8, abs=0.08)
    assert spf.alpha == pytest.approx(0.3, abs=0.1)
    assert spf.n == 3000
    mu = spf.predict({"log_flow": math.log(10000)}, math.log(2.0))
    assert mu == pytest.approx(math.exp(-9.0) * 2 * 10000**0.8, rel=0.3)


def _poisson(rng, lam):
    # Knuth for small lambda, normal approximation above
    if lam > 50:
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    k, p, limit = 0, 1.0, math.exp(-lam)
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _unit(i, observed, aadf, length=1.0, family=("principal_a", "single", "urban")):
    return {
        "unit_type": "link",
        "unit_id": str(i),
        "family": family,
        "urban": True,
        "region": "england",
        "observed": observed,
        "ksi": 0,
        "fatal": 0,
        "length_km": length,
        "flow": aadf,
        "flow_estimated": None,
        "flag": None,
        "features": {"log_flow": math.log(aadf)},
        "offset": math.log(length),
        "geom": None,
    }


def test_score_fits_each_group_and_ranks_by_excess():
    from stats19.reference.safety_build import _score

    rng = random.Random(3)
    units = []
    for i in range(400):
        aadf = rng.uniform(5000, 40000)
        mu = math.exp(-7.5) * aadf**0.85
        units.append(_unit(i, _poisson(rng, rng.gammavariate(2.5, mu / 2.5)), aadf))
    units.append(_unit("hot", 60, 15000))  # far worse than similar roads
    units += [_unit(f"m{i}", 3, 20000, family=("motorway", "dual", "rural")) for i in range(5)]

    rows, models = _score(units)

    by_id = {r[1]: r for r in rows}
    hot = by_id["hot"]
    assert hot[2] == "principal_a/single/urban" and hot[13] == 1  # excess rank 1
    assert hot[11] > 0 and hot[9] < hot[10] < 60  # predicted < EB < observed
    assert hot[14] == 401  # group size
    assert by_id["m0"][2] == "motorway" and by_id["m0"][9] is None  # 5 sites: no model
    assert [m[1] for m in models] == ["principal_a/single/urban"]
    # the group's severity totals travel with its model, for valuing its collisions
    assert models[0][7] == sum(u["observed"] for u in units[:401])
    assert models[0][8:] == (0, 0)


def test_value_per_collision_follows_the_severity_mix():
    from stats19.api.prevention import value_per_collision

    values = {1: 2_000_000.0, 2: 300_000.0, 3: 30_000.0}

    # 100 collisions: 1 fatal, 9 serious, 90 slight
    got = value_per_collision(observed=100, ksi=10, fatal=1, values=values)

    assert got == pytest.approx((2_000_000 + 9 * 300_000 + 90 * 30_000) / 100)
    assert value_per_collision(0, 0, 0, values) is None
    assert value_per_collision(5, 1, 0, {1: 0.0, 2: 0.0, 3: 0.0}) is None


def test_risk_layer_thins_junctions_when_zoomed_out():
    from stats19.api.safety import junction_min_band

    assert junction_min_band(8) is None
    assert junction_min_band(9) == 2  # worst 5%
    assert junction_min_band(12) == 2
    assert junction_min_band(13) == 1  # worst 20%
    assert junction_min_band(15) == -1  # everything


@pytest.mark.parametrize(
    ("code", "region"),
    [
        ("E09000033", "london"),
        ("S12000036", "scotland"),
        ("W06000015", "wales"),
        ("E10000008", "england"),
        (None, "england"),
    ],
)
def test_region_from_authority_code(code, region):
    from stats19.reference.safety import region_of

    assert region_of(code) == region


def test_region_level_keeps_london_sites_from_all_looking_worse():
    """London records twice the collisions of similar roads elsewhere: compare like with like."""
    import json

    from stats19.reference.safety import region_features
    from stats19.reference.safety_build import _score

    rng = random.Random(11)
    national, regional = [], []
    for i in range(600):
        region = "london" if i % 3 == 0 else "england"
        aadf = rng.uniform(5000, 40000)
        mu = math.exp(-7.5) * aadf**0.85 * (2.0 if region == "london" else 1.0)
        u = _unit(i, _poisson(rng, rng.gammavariate(4, mu / 4)), aadf) | {"region": region}
        national.append(u)
        regional.append(u | {"features": u["features"] | region_features(region)})

    def london_share_of_worst_5pct(rows):
        worst = [r for r in rows if r[13] <= 0.05 * r[14]]
        return sum(r[5] == "london" for r in worst) / len(worst)

    rows_national, _ = _score(national)
    rows_regional, models = _score(regional)

    assert json.loads(models[0][4])["region_london"] == pytest.approx(math.log(2), abs=0.15)

    def london_mean_excess(rows):
        return sum(r[11] for r in rows if r[5] == "london") / 200

    # one national level: every London site's excess is inflated by the reporting level
    assert london_mean_excess(rows_national) > 3 * abs(london_mean_excess(rows_regional))
    # ranked among similar sites in their own region: a third of the worst, like the rest
    assert london_share_of_worst_5pct(rows_regional) == pytest.approx(1 / 3, abs=0.05)
    assert {r[14] for r in rows_regional if r[5] == "london"} == {200}  # group size per region


def test_typical_minor_flows_are_medians_by_class_and_setting():
    samples = [("Unclassified", True, f) for f in (400, 600, 800)] + [
        ("Unclassified", False, f) for f in (100, 200, 300)
    ]

    typical = typical_minor_flows(samples, min_samples=3)

    assert typical("Unclassified", urban=True) == 600
    assert typical("Unclassified", urban=False) == 200
    assert typical("Not Classified", urban=False) == 200  # OS's other minor classes: as U


def test_typical_minor_flows_fall_back_to_the_class_then_all_minor_roads():
    samples = [("B Road", True, f) for f in (5000, 7000, 9000)] + [
        ("B Road", False, 3000),
        ("Classified Unnumbered", True, 1500),
    ]

    typical = typical_minor_flows(samples, min_samples=3)

    assert typical("B Road", urban=False) == 6000  # too few rural B samples: all B roads
    assert typical("Motorway", urban=True) == 5000  # no motorway samples: every minor arm
