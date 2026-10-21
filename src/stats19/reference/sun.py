"""Sun position and each vehicle's heading at a collision (PLAN-012 C1, FU-043).

Pure functions on numpy arrays, so the maths is unit-tested without a database.

- **Clock time to UTC.** STATS19 records local clock time. ``local_to_utc`` uses the
  Europe/London rules from ``zoneinfo``, which hold every change back to 1972, so BST is
  right in every year from 1979. An hour that happens twice (the autumn change) takes the
  first; an hour that doesn't exist (the spring change) is read as GMT.
- **Sun position.** NOAA's solar-position equations (the NOAA Solar Calculator's), with
  its correction for atmospheric refraction. Within a few hundredths of a degree of NREL's
  SPA over 1979–2100 (tests/test_sun.py), far better than this needs.
- **Heading.** A vehicle's direction of travel in degrees from true north. From the OS
  link it was matched to where that's trustworthy, with the police compass choosing which
  way along it; otherwise from the compass alone (±22.5°). See ``headings``.
- **Bands** (D4): low sun is 0–15° up; "ahead" is within 30° of the heading, "behind"
  within 30° of the reverse.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np

LONDON = ZoneInfo("Europe/London")
LOW_SUN_DEG = 15.0
AHEAD_DEG = 30.0
# a link direction is trusted only when the compass agrees with it to within this: further
# out, the collision was probably matched to a crossing road, so the compass decides
LINK_AGREES_DEG = 67.5
COMPASS = {k: 45.0 * (k - 1) for k in range(1, 9)}  # STATS19 1 = North ... 8 = North West

SOURCE_LINK = "link"
SOURCE_COMPASS = "compass"

BANDS = ("dark", "low_ahead", "low_behind", "low_side", "high", "unknown")


# ------------------------------------------------------------------ time


def utc_offset_s(day: date, clock: time) -> int:
    """Seconds to subtract from a London clock time to get UTC (0 or 3600)."""
    local = datetime.combine(day, clock).replace(tzinfo=LONDON, fold=0)
    # a clock time skipped in spring: zoneinfo reads it with the offset before the change
    offset = local.utcoffset()
    return int(offset.total_seconds()) if offset else 0


def local_to_utc(days: np.ndarray, clocks: np.ndarray) -> np.ndarray:
    """UTC epoch seconds for London clock times: ``days`` as datetime64[D], ``clocks`` as
    seconds after midnight. Offsets are worked out per day at noon, and per row only on
    the days the clocks change."""
    days = days.astype("datetime64[D]")
    epoch = days.astype("int64") * 86400 + clocks.astype("int64")
    unique = np.unique(days)
    noon = time(12)
    offsets = np.empty(len(unique), dtype="int64")
    changes = []
    for i, d in enumerate(unique.astype(object)):
        offsets[i] = utc_offset_s(d, noon)
        if utc_offset_s(d, time(0, 30)) != utc_offset_s(d, time(23, 30)):
            changes.append(d)
    out = epoch - offsets[np.searchsorted(unique, days)]
    for d in changes:
        rows = np.nonzero(days == np.datetime64(d))[0]
        for r in rows:
            clock = (datetime.min + timedelta(seconds=int(clocks[r]))).time()
            out[r] = epoch[r] - utc_offset_s(d, clock)
    return out


# ------------------------------------------------------------------ sun


def solar_position(epoch_s: np.ndarray, lat: np.ndarray, lon: np.ndarray) -> tuple:
    """(elevation, azimuth) in degrees for UTC epoch seconds at WGS84 lat/lon: elevation
    above the horizon with refraction, azimuth clockwise from true north. NOAA's equations."""
    jd = epoch_s / 86400.0 + 2440587.5
    jc = (jd - 2451545.0) / 36525.0
    l0 = np.mod(280.46646 + jc * (36000.76983 + jc * 0.0003032), 360.0)
    m = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    e = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    mr = np.radians(m)
    centre = (
        np.sin(mr) * (1.914602 - jc * (0.004817 + 0.000014 * jc))
        + np.sin(2 * mr) * (0.019993 - 0.000101 * jc)
        + np.sin(3 * mr) * 0.000289
    )
    omega = np.radians(125.04 - 1934.136 * jc)
    apparent = l0 + centre - 0.00569 - 0.00478 * np.sin(omega)
    mean_obliquity = 23 + (26 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60) / 60
    obliquity = np.radians(mean_obliquity + 0.00256 * np.cos(omega))
    decl = np.arcsin(np.sin(obliquity) * np.sin(np.radians(apparent)))
    y = np.tan(obliquity / 2) ** 2
    l0r = np.radians(l0)
    eq_time = 4 * np.degrees(
        y * np.sin(2 * l0r)
        - 2 * e * np.sin(mr)
        + 4 * e * y * np.sin(mr) * np.cos(2 * l0r)
        - 0.5 * y * y * np.sin(4 * l0r)
        - 1.25 * e * e * np.sin(2 * mr)
    )
    minutes = np.mod(epoch_s, 86400.0) / 60.0
    true_solar = np.mod(minutes + eq_time + 4 * lon, 1440.0)
    hour_angle = np.where(true_solar / 4 < 0, true_solar / 4 + 180, true_solar / 4 - 180)
    latr = np.radians(lat)
    cos_zen = np.sin(latr) * np.sin(decl) + np.cos(latr) * np.cos(decl) * np.cos(
        np.radians(hour_angle)
    )
    zenith = np.arccos(np.clip(cos_zen, -1.0, 1.0))
    elevation = 90 - np.degrees(zenith)
    with np.errstate(divide="ignore", invalid="ignore"):
        cos_az = (np.sin(latr) * np.cos(zenith) - np.sin(decl)) / (np.cos(latr) * np.sin(zenith))
    az = np.degrees(np.arccos(np.clip(cos_az, -1.0, 1.0)))
    azimuth = np.where(hour_angle > 0, np.mod(az + 180, 360), np.mod(540 - az, 360))
    return elevation + _refraction(elevation), azimuth


def _refraction(elevation: np.ndarray) -> np.ndarray:
    """NOAA's atmospheric refraction correction, in degrees."""
    e = elevation
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.tan(np.radians(e))
        high = (58.1 / t - 0.07 / t**3 + 0.000086 / t**5) / 3600
        low = (1735 + e * (-518.2 + e * (103.4 + e * (-12.79 + e * 0.711)))) / 3600
        below = (-20.772 / t) / 3600
    return np.select([e > 85, e > 5, e > -0.575], [0.0, high, low], below)


# ------------------------------------------------------------------ heading


def angle_diff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """a − b, wrapped to −180..180 (negative: a is anticlockwise of b, i.e. to the left)."""
    return np.mod(np.asarray(a) - np.asarray(b) + 180.0, 360.0) - 180.0


def compass_heading(direction_from: np.ndarray, direction_to: np.ndarray) -> np.ndarray:
    """Heading from STATS19's compass points; NaN for parked, unknown or missing.

    "To" is where the vehicle was heading, so a turning vehicle (from N to E) gets its
    heading after the turn. Without a "to", the reverse of "from" stands in."""
    to = np.asarray(direction_to)
    frm = np.asarray(direction_from)
    out = np.full(to.shape, np.nan)
    has_to = (to >= 1) & (to <= 8)
    out[has_to] = 45.0 * (to[has_to] - 1)
    only_from = ~has_to & (frm >= 1) & (frm <= 8)
    out[only_from] = np.mod(45.0 * (frm[only_from] - 1) + 180.0, 360.0)
    return out


def headings(
    compass: np.ndarray, link_bearing: np.ndarray, at_junction: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """(heading, source) per vehicle.

    The link's bearing (along its digitised direction, NaN without a link) is used away
    from junctions, taking whichever way along it is nearer the compass heading, if that's
    within LINK_AGREES_DEG. Otherwise the compass heading. No compass, no heading: the link
    alone can't say which way the vehicle went."""
    compass = np.asarray(compass, dtype=float)
    bearing = np.asarray(link_bearing, dtype=float)
    reverse = np.mod(bearing + 180.0, 360.0)
    forward_off = np.abs(angle_diff(bearing, compass))
    reverse_off = np.abs(angle_diff(reverse, compass))
    along = np.where(forward_off <= reverse_off, bearing, reverse)
    off = np.minimum(forward_off, reverse_off)
    use_link = (
        ~np.isnan(compass)
        & ~np.isnan(bearing)
        & ~np.asarray(at_junction, dtype=bool)
        & (off <= LINK_AGREES_DEG)
    )
    heading = np.where(use_link, along, compass)
    source = np.where(
        use_link, SOURCE_LINK, np.where(np.isnan(compass), None, SOURCE_COMPASS)
    ).astype(object)
    return heading, source


def sun_bands(elevation: np.ndarray, relative: np.ndarray) -> np.ndarray:
    """The sun band (D4) from its elevation and its bearing relative to the heading (NaN
    without a heading). Dark needs no heading; the low-sun bands do."""
    elevation = np.asarray(elevation, dtype=float)
    relative = np.asarray(relative, dtype=float)
    low = (elevation >= 0) & (elevation <= LOW_SUN_DEG)
    ahead = np.abs(relative) <= AHEAD_DEG
    behind = np.abs(relative) >= 180.0 - AHEAD_DEG
    known = ~np.isnan(relative)
    return np.select(
        [
            np.isnan(elevation),
            elevation < 0,
            elevation > LOW_SUN_DEG,
            low & known & ahead,
            low & known & behind,
            low & known,
        ],
        ["unknown", "dark", "high", "low_ahead", "low_behind", "low_side"],
        "unknown",
    ).astype(object)
