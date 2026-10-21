"""Similar authorities from open measures (PLAN-009 §10.3)."""

import math

import pytest

from stats19.reference.authorities import (
    AuthorityMeasures,
    country_group,
    nearest_peers,
    peer_features,
    peers_within_country,
    recording_gaps,
)


def measures(pop, area, vkm, major, road):
    return AuthorityMeasures(
        population=pop, area_km2=area, vehicle_km=vkm, major_vehicle_km=major, road_km=road
    )


def test_peer_features_are_log_scaled_rates_and_the_major_share():
    got = peer_features(measures(200_000, 100.0, 2e9, 1e9, 1_000.0))

    assert got == pytest.approx(
        (math.log(200_000), math.log(2_000), math.log(10_000), 0.5, math.log(5.0))
    )  # people, people per km², vehicle-km a head, major share, road km per 1,000 people


@pytest.mark.parametrize(
    "bad",
    [
        measures(0, 100.0, 2e9, 1e9, 1_000.0),
        measures(200_000, 100.0, None, 1e9, 1_000.0),
        measures(200_000, 100.0, 2e9, None, 1_000.0),
    ],
)
def test_peer_features_need_every_measure(bad):
    assert peer_features(bad) is None


def test_nearest_peers_are_the_closest_after_standardising():
    # two clusters: dense cities and rural counties; scale differs wildly between measures
    features = {
        "city_a": (13.0, 8.0, 8.0, 0.30, 1.0),
        "city_b": (13.1, 8.1, 8.1, 0.32, 1.1),
        "city_c": (12.9, 7.9, 8.0, 0.29, 0.9),
        "shire_a": (13.5, 5.0, 9.5, 0.60, 2.5),
        "shire_b": (13.4, 5.1, 9.4, 0.62, 2.4),
    }

    got = nearest_peers(features, k=2)

    assert [code for code, _ in got["city_a"]] == ["city_b", "city_c"] or [
        code for code, _ in got["city_a"]
    ] == ["city_c", "city_b"]
    assert [code for code, _ in got["shire_a"]][0] == "shire_b"
    assert all(code != "city_a" for code, _ in got["city_a"])  # never its own peer
    assert got["city_a"][0][1] <= got["city_a"][1][1]  # nearest first


def test_nearest_peers_caps_k_at_the_others_available():
    got = nearest_peers({"a": (1.0, 1.0, 1.0, 0.1, 1.0), "b": (2.0, 2.0, 2.0, 0.2, 2.0)}, k=15)

    assert [c for c, _ in got["a"]] == ["b"]


def test_peers_come_from_the_same_country():
    # FU-047: Bath's peers included Scottish and Welsh councils, which record far fewer
    # collisions per vehicle-km
    features = {
        "bath": (12.2, 6.0, 9.0, 0.5, 1.7),
        "england_twin": (12.3, 6.1, 9.1, 0.5, 1.8),
        "england_far": (14.0, 8.0, 8.0, 0.2, 0.5),
        "scot_twin": (12.2, 6.0, 9.0, 0.5, 1.7),  # identical measures, other country
    }
    regions = {
        "bath": "South West",
        "england_twin": "South East",
        "england_far": "London",
        "scot_twin": "Scotland",
    }

    got = peers_within_country(features, regions, k=5)

    assert [c for c, _ in got["bath"]] == ["england_twin"]  # not the Scottish twin, not London
    assert got["scot_twin"] == []
    assert country_group("Wales") == "wales" and country_group(None) == "england"


def test_recording_gaps_flag_years_far_below_the_usual_share():
    gb = {y: 100_000 for y in range(2019, 2026)}
    counts = {2019: 190, 2020: 185, 2021: 188, 2022: 190, 2023: 76, 2024: 187, 2025: 189}

    assert recording_gaps(counts, gb) == {2023: pytest.approx(76 / 188, abs=0.01)}


def test_recording_gaps_follow_the_national_trend_and_need_enough_years():
    gb = {2019: 120_000, 2020: 90_000, 2021: 100_000, 2022: 100_000, 2023: 100_000}
    covid = {2019: 120, 2020: 90, 2021: 100, 2022: 100, 2023: 100}  # falls with GB: no gap

    assert recording_gaps(covid, gb) == {}
    assert recording_gaps({2024: 1}, {2024: 100}) == {}


def test_a_steady_decline_is_not_a_gap():
    # Scotland: recorded collisions fell steadily for 20 years, faster than GB
    gb = {y: 100_000 for y in range(2006, 2026)}
    declining = {y: round(400 * 0.94 ** (y - 2006)) for y in gb}

    assert recording_gaps(declining, gb) == {}


def test_small_authorities_are_too_noisy_to_judge():
    gb = {y: 100_000 for y in range(2019, 2026)}
    scilly = {2019: 6, 2020: 0, 2021: 0, 2022: 5, 2023: 7, 2024: 6, 2025: 5}

    assert recording_gaps(scilly, gb) == {}


def test_a_gap_of_several_years_is_still_found():
    # Stoke-on-Trent 2021-23
    gb = {y: 100_000 for y in range(2015, 2026)}
    stoke = {y: 400 for y in gb} | {2021: 190, 2022: 100, 2023: 190}

    assert set(recording_gaps(stoke, gb)) == {2021, 2022, 2023}
