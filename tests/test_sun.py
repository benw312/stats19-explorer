"""Sun position, clock time and heading (PLAN-012 C1): stats19.reference.sun."""

from datetime import date, time

import numpy as np
import pytest

from stats19.reference import sun

# (UTC, lat, lon, elevation, azimuth) from NREL's SPA (pvlib 0.13 spa_python, 1013.25 hPa,
# 10 °C): an independent, more exact algorithm. Summer noon in London, a winter dawn in
# Edinburgh, Cornwall in 1979, Manchester on a BST changeover morning, sunset in Cambridge,
# Shetland in 2099 and night in Bristol.
SPA = [
    ("2024-06-21T12:00:00", 51.5007, -0.1246, 61.9402, 178.8201),
    ("2024-12-21T08:30:00", 55.9533, -3.1883, -2.1077, 131.0361),
    ("1979-01-01T15:45:00", 50.1, -5.55, 4.8091, 224.8829),
    ("1995-03-26T07:10:00", 53.4808, -2.2426, 9.9054, 99.9390),
    ("2010-09-23T17:50:00", 52.2053, 0.1218, 0.5612, 269.4934),
    ("2099-07-01T03:30:00", 60.153, -1.149, 2.9716, 45.1525),
    ("2016-11-05T22:00:00", 51.4545, -2.5879, -47.9177, 316.8276),
]


def epoch(iso: str) -> float:
    return float(np.datetime64(iso, "s").astype("int64"))


@pytest.mark.parametrize("utc, lat, lon, elevation, azimuth", SPA)
def test_noaa_agrees_with_spa(utc, lat, lon, elevation, azimuth):
    el, az = sun.solar_position(np.array([epoch(utc)]), np.array([lat]), np.array([lon]))
    # the refraction models differ near the horizon, and below it NOAA still adds a little
    # (0.16° at −2°) where SPA adds none: neither matters for "dark" or "low"
    tolerance = 0.03 if elevation > 1 else 0.1 if elevation > -1 else 0.2
    assert el[0] == pytest.approx(elevation, abs=tolerance)
    assert az[0] == pytest.approx(azimuth, abs=0.03)


def test_clock_time_is_bst_in_summer_and_gmt_in_winter():
    days = np.array(["2024-07-01", "2024-01-15"], dtype="datetime64[D]")
    clocks = np.array([9 * 3600, 9 * 3600])

    utc = sun.local_to_utc(days, clocks)

    assert list(utc - days.astype("int64") * 86400) == [8 * 3600, 9 * 3600]


def test_bst_changeover_days_switch_at_the_right_hour():
    # 31 March 2024: clocks went forward at 01:00 GMT. 27 October 2024: back at 02:00 BST.
    days = np.array(
        ["2024-03-31", "2024-03-31", "2024-03-31", "2024-10-27", "2024-10-27", "2024-10-27"],
        dtype="datetime64[D]",
    )
    clocks = np.array([0.5, 1.5, 2.5, 0.5, 1.5, 2.5]) * 3600

    utc = sun.local_to_utc(days, clocks) - days.astype("int64") * 86400

    hours = list(utc / 3600)
    # 01:30 on 31 March never happened: read as GMT. 01:30 on 27 October happened twice:
    # the first (BST).
    assert hours == [0.5, 1.5, 1.5, -0.5, 0.5, 2.5]


def test_bst_rules_from_the_1980s_are_used():
    # 1981 was the first year of the EU last-Sunday rule: BST began 29 March. In 1980 it
    # began on 16 March, so 23 March 1980 was BST and 23 March 1981 wasn't.
    assert sun.utc_offset_s(date(1980, 3, 23), time(12)) == 3600
    assert sun.utc_offset_s(date(1981, 3, 23), time(12)) == 0


@pytest.mark.parametrize(
    "frm, to, want",
    [
        (1, 5, 180.0),  # from the north, heading south
        (7, 3, 90.0),  # west to east
        (1, 3, 90.0),  # turning: its heading after the turn
        (2, -1, 225.0),  # no "to": the reverse of "from" (NE → SW)
        (0, 0, None),  # parked
        (9, 9, None),  # unknown
    ],
)
def test_compass_heading(frm, to, want):
    h = sun.compass_heading(np.array([frm]), np.array([to]))[0]
    assert np.isnan(h) if want is None else h == want


def test_heading_takes_the_link_way_nearer_the_compass():
    compass = np.array([180.0, 0.0, 90.0, 90.0, np.nan])
    # a link digitised at 10°: southbound traffic goes along it reversed (190°), northbound
    # along it (10°); a link at 0° can't be trusted for an eastbound vehicle (90° out), nor
    # at a junction; without a compass there's no heading
    bearing = np.array([10.0, 10.0, 0.0, 85.0, 10.0])
    junction = np.array([False, False, False, True, False])

    heading, source = sun.headings(compass, bearing, junction)

    assert list(heading[:4]) == [190.0, 10.0, 90.0, 90.0] and np.isnan(heading[4])
    assert list(source) == ["link", "link", "compass", "compass", None]


def test_relative_angle_is_negative_to_the_left():
    assert sun.angle_diff(np.array([350.0]), np.array([10.0]))[0] == -20.0
    assert sun.angle_diff(np.array([10.0]), np.array([350.0]))[0] == 20.0
    assert abs(sun.angle_diff(np.array([180.0]), np.array([0.0]))[0]) == 180.0


def test_sun_bands():
    elevation = np.array([-3.0, 40.0, 8.0, 8.0, 8.0, 8.0, np.nan, 15.0])
    relative = np.array([0.0, 0.0, -25.0, 170.0, 90.0, np.nan, 0.0, 30.0])

    bands = sun.sun_bands(elevation, relative)

    assert list(bands) == [
        "dark",
        "high",
        "low_ahead",
        "low_behind",
        "low_side",
        "unknown",  # low sun, but no heading
        "unknown",  # no time
        "low_ahead",  # 15° up, 30° off: the edges count
    ]


def test_glare_ratio_is_fine_over_rain_with_a_woolf_interval():
    from stats19.reference.context_check import Ratio

    r = Ratio("link", fine_ahead=1200, fine_behind=1000, rain_ahead=100, rain_behind=100)

    g, lo, hi = r.glare()

    assert g == pytest.approx(1.2)
    se = (1 / 1200 + 1 / 1000 + 1 / 100 + 1 / 100) ** 0.5
    assert lo == pytest.approx(1.2 * np.exp(-1.959964 * se))
    assert hi == pytest.approx(1.2 * np.exp(1.959964 * se))
    assert np.isnan(Ratio("compass", 5, 0, 1, 1).glare()[0])
