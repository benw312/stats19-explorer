# PLAN-012 — Collision context: low sun and road gradient

- **Status:** AGREED 2026-10-10: all six decisions in §8 as recommended. C1 built 2026-10-11 (see §10).
- **Covers:** FU-043 (sun position against the direction of travel) and FU-044 (road gradient). PLAN-010 §1 item 4, about a week.
- **Why together:**
  - Both are computed once per collision (or per vehicle) in the pipeline, from data we already have or can load once.
  - Both are shown the same way: a filter, a line on the record panel, and a "compared with similar sites" figure on site pages.
  - Both need each vehicle's **heading**, so that's built once and shared (§3).

## 1. What the engineer gets

1. **On the record panel**, for each moving vehicle:
   - "Sun 8° above the horizon, 12° left of the direction of travel (low sun ahead)."
   - "Travelling downhill, about 6% (OS Terrain 50)."

   Each line is stated as a condition, never as a cause (FU-001).
2. **Two new filters** under Conditions:
   - **Sun:** low sun ahead / low sun behind / sun up / dark.
   - **Gradient:** level / 3–5% / 5–8% / over 8%, uphill or downhill.

   Both work everywhere filters do: maps, summaries, exports and reports.
3. **On site pages, in "What's different":**
   - the share of the site's collisions with a low sun ahead, against the authority, with the usual over-representation test;
   - the same for steep downhill approaches.

   This is the useful view: an east–west approach that keeps appearing at sunrise or sunset.
4. **Routes (later, optional):** an elevation profile under the strip chart, from the same terrain samples.

## 2. Data

| Need | Source | Have it? |
|---|---|---|
| Time and place | `core.collision`: date, time (local clock time) and `geom_bng` | Yes. Only 8 collisions have no time |
| Direction of travel | `core.vehicle.vehicle_direction_from` / `_to`: 8 compass points; 0 = parked, 9 = unknown, −1 = missing | Yes. In 2024, about 74% of vehicles have a usable direction |
| The road at the collision | `geo.collision_link`: the OS link, and `frac` along it (FU-037) | Yes, for collisions matched to a link |
| Sun position | Computed from the NOAA solar-position equations. Nothing to download | — |
| Ground height | **OS Terrain 50**: 50 m grid, all of GB, OGL. ASCII grid, 2,858 tiles of 10 km, **157 MB compressed**, no registration | To load (C2) |
| Bridges and tunnels | OSM `bridge=*` / `tunnel=*` ways, from the Geofabrik extract the signals already come from (`osm_nodes.py`) | To add: a ways pass alongside the nodes pass |
| Weather | `weather_conditions`: "fine" is the nearest thing to a clear sky | Yes |

## 3. Heading: shared by both

- **Matched to a link:** the link's bearing at `frac` (the segment containing that point). The vehicle's compass direction then only chooses which way along the link it was going: the end nearer the recorded "to" direction. That gives a heading to a few degrees.
- **Not matched, or at a junction:** the compass `from → to` bearing (±22.5°). A turning vehicle (from N to E) gets the "to" direction, its heading after the turn. It's flagged as approximate.
- **Parked, unknown or missing (0, 9, −1):** no heading. Sun and gradient fall back to the collision level only (elevation, and the link's grade without a sign).
- Stored per vehicle: `heading_deg` and `heading_source` (`link` / `compass`).

## 4. Sun (C1)

- **Method:**
  - NOAA's solar-position equations, vectorised in numpy, about 60 lines. It's accurate to well under 1° from 1979 to 2100, which is plenty. A new dependency (pvlib) isn't needed, see D1.
  - **Time:** STATS19 times are local clock times. Convert to UTC with `zoneinfo` "Europe/London", so BST is handled, including the historic rules back to 1979.
- **Stored per vehicle**, in a new derived table `mart.vehicle_context`, rebuilt as a new step `context` after `collision_links`:
  - `sun_elevation_deg`;
  - `sun_relative_deg`: the sun's bearing minus the heading, in −180 to 180, negative meaning left;
  - `sun_band`:

| Band | Rule (D4) |
|---|---|
| `dark` | Elevation below 0° |
| `low_ahead` | 0–15° elevation, within ±30° of the heading |
| `low_behind` | 0–15°, within ±30° of the heading reversed: in the mirrors, and in oncoming drivers' eyes |
| `low_side` | 0–15°, any other bearing |
| `high` | Above 15° |
| `unknown` | No heading, or no time |

- **Speed:** about 20 million vehicle rows over 47 years. That's arithmetic only, so a minute or two on the BOSGAME.
- **Validation:**
  - The police "dazzling sun" factor isn't in the open data, so collisions can't be checked one by one.
  - Instead, a check like the safety-check command: on east–west links, `low_ahead` should be clearly over-represented near sunrise and sunset, against the same links at other times.
  - If it isn't, the thresholds or the heading are wrong. The result goes in the PR.

## 5. Gradient (C2)

- **Loading the terrain:**
  - `stats19 refresh-reference --dataset terrain50` downloads the national ASCII grid from the OS Data Hub.
  - It stores the heights as one PostGIS raster table, `geo.terrain50`: tiled 100 × 100 cells, with a spatial index, about 1–2 GB in the database.
  - It's refreshed like the other reference data (OS updates it yearly; the 90-day staleness check is enough).
- **Along a matched link:**
  - Sample heights at the collision's `frac`, ±50 m along the link (bilinear, `ST_Value(..., 'bilinear')`).
  - Grade = Δh / 100 m, signed in the link's digitised direction.
  - Per vehicle: uphill or downhill from its heading against the link's direction. Level is under 3% (D5).
- **Not matched:** the four-point slope (heights 25 m N, S, E and W), projected onto the compass heading. It's flagged `source = 'terrain_point'`.
- **Bridges and tunnels:**
  - A collision on a link that crosses an OSM bridge or tunnel within 50 m gets no grade.
  - A terrain model is bare earth: a viaduct would get the valley's slope.
  - Stored as `grade_note = 'bridge' | 'tunnel'`.
- **Stored:**
  - per collision: `grade_pct`, `grade_source`;
  - per vehicle: `grade_band` (`level`, `up_3_5`, `up_5_8`, `up_8`, `down_3_5`, `down_5_8`, `down_8`, `unknown`).
- **Shown as bands, never as exact percentages:** Terrain 50 smooths short steep sections, and the bands say so.
- **Per link (for Routes later):** a height profile every 50 m along each OS link with collisions, in `geo.link_profile`.

## 6. App (C3)

- **Filters:**
  - "Sun" and "Gradient" chip groups under Conditions;
  - they're added to `stats19.api.filters` as vehicle-level conditions, like the road-user filter (any vehicle in the collision matches);
  - the codes are documented in the field guide and the About page.
- **Record panel:** one line per vehicle under its manoeuvre. The wording is in §1.
- **Site pages, "What's different":**
  - two rows using the existing over-representation test: "Low sun ahead" and "Steep downhill (over 5%)";
  - each counted against the same filter over the authority;
  - nothing new on the API, beyond the two new fields being available to `compare`.
- **About page:** how the sun and gradient are worked out, what they can't see (hills hiding a low sun, buildings, Terrain 50's smoothing), and that they're conditions, not causes.
- **PDFs:** the record line in the collision report, and the rows in the site report's "What's different".

## 7. Phases (each a PR)

| Phase | Content | Size |
|---|---|---|
| C1 | Heading (§3) and sun (§4). `mart.vehicle_context` and the `context` derived step. Unit tests: NOAA values against the NOAA calculator for fixed times and places; BST changeover days; the headings worked by hand. The validation check | 2 days |
| C2 | Terrain 50 load; gradient along links and at points (§5); OSM bridges and tunnels. Tests on a synthetic raster with a known slope; a bridge fixture | 2½ days |
| C3 | Filters, record panel, site rows, About page, PDFs (§6). Field-guide entries | 1½ days |
| — | BOSGAME: `refresh-reference --dataset terrain50` (about 10 minutes plus the download), then `rebuild-derived --step context` (a few minutes). Both announced in C2's PR | you, ¼ hour |

**Later, not in this plan:**
- lidar where it exists (EA LIDAR Composite DTM for England, NRW lidar for Wales), loaded per authority on request and recorded as the source;
- the hill horizon for a low sun (is the sun actually visible over the terrain?);
- grade as a variable in the safety model's peer groups.

## 8. Decisions (agreed 2026-10-10, all as recommended)

- **D1. Sun maths: our own NOAA code (recommended), or the `pvlib` library?**
  - Ours is about 60 lines, tested against NOAA's published calculator, and adds no dependency.
  - pvlib is excellent, but it's large (it pulls in pandas, which the API image doesn't otherwise need).
- **D2. Terrain: Terrain 50 for all of GB first, lidar later (recommended)?** Or wait and do lidar for England from the start?
  - Lidar is much better for short steep sections, but it's big and patchy. Each grade records its source, so lidar can replace Terrain 50 later.
- **D3. Heading: the link's bearing, with the compass to choose the way (recommended)?** Or the compass only?
  - The compass alone is ±22.5°. That's coarse for a ±30° "ahead" test.
- **D4. Low-sun thresholds: under 15° elevation, within ±30° of the heading (recommended, PLAN-002's draft rule)?**
  - A tighter rule (10°, ±20°) gives fewer, surer cases. The validation in C1 may suggest moving them; I'd report that rather than change them silently.
- **D5. Gradient bands: level under 3%, then 3–5%, 5–8% and over 8% (recommended)?**
  - DMRB CD 109's maximum gradients for new roads fall in this range, depending on road type: check the breaks against the edition you use. Or use the breaks your authority uses.
- **D6. Where it shows first:** all of §6 in C3 (recommended)? Or the record panel and filters only, with the site rows after a pilot user asks?

## 9. Risks

- **The heading is the weak link.**
  - A quarter of vehicles have no usable direction.
  - At junctions the link's bearing is ambiguous, so the compass decides (±22.5°).
  - The record panel says "approximate" for compass headings.
- **Over-reading.** A filter called "low sun ahead" invites "glare caused it". The wording and the About page keep to conditions, as FU-001 requires, and the site comparison is the honest use.
- **Terrain 50 is smoothed.** A 10% ramp of 40 m reads as about 4%. The bands and the source label make that visible. Lidar fixes it later.
- **Raster in PostGIS.** `postgis_raster` must be enabled. The PostGIS image has it, but the extension is created in C2's migration, and a missing extension fails loudly at load, never silently.

## 10. As built

### C1 (2026-10-11)

**The maths: `stats19.reference.sun`.** These are pure numpy functions, tested in `tests/test_sun.py`.
- **Clock time to UTC** uses `zoneinfo` Europe/London, worked out per day and per row only on changeover days.
  - A skipped spring hour is read as GMT.
  - A repeated autumn hour takes the first (BST).
  - Tested on both 2024 changeovers, and on 1980 against 1981, the year the last-Sunday rule began.
- **Sun position** uses NOAA's equations with its refraction correction (D1: our own code, no pvlib).
  - Checked against NREL's SPA (pvlib, outside the project) at seven times and places from 1979 to 2099.
  - Within 0.03° above 1° of elevation.
  - Below the horizon, NOAA adds up to 0.2° of refraction that SPA doesn't; it doesn't matter for "dark".
- **Heading** (D3): the compass's "to" point (a turning vehicle gets its heading after the turn), or the reverse of "from" when there's no "to".
  - Where the collision is matched to an OS link and isn't a junction collision, the link's bearing replaces the compass. The compass chooses which way along the link, and only if that's within 67.5° of it; further out, the match is probably a crossing road.
  - The link bearing is taken over 20 m either side of the collision, as a true-north azimuth on the ellipsoid. OS grid north is up to ~4° off true north across GB.
- **Bands** (D4, unchanged): 0–15° up, within 30° of the heading (ahead) or of its reverse (behind).
  - "Dark" and "high" don't need a heading.

**The tables: the `context` derived step** (`stats19.reference.context_build`). It runs after `collision_links`, and is rebuilt when STATS19 or the road network loads.
- **`geo.collision_context`:** the sun's elevation and azimuth for every collision with a time and a place (9.1 M).
- **`geo.vehicle_context`:** for every vehicle with a heading (15.1 M of 16.3 M), the heading, its source (`link` or `compass`), the sun's bearing relative to it, and the band.
- **They're in `geo`, not `mart` as §4 said:** the mart schema is replaced whole on every load, which would drop them.
- **On the Mac:** 3 minutes for 1979–2025, at most 1.1 GB of memory, and 2.2 GB on disk (10% of the database).
- **Link headings cover only the last 10 years** (the link matches, FU-037), and only away from junctions: 0.67 M vehicles. Everything else uses the compass.

**Validation: `stats19 context-check`.**
- **The idea:** traffic runs both ways at the same times, so without glare "low sun ahead" should be about as common as "low sun behind". Rain means no direct sun, so it's the control.
- **On the full data, 2006–2025:**

| Heading from | Fine: ahead ÷ behind | Rain: ahead ÷ behind | Fine ÷ rain (95% CI) |
|---|---|---|---|
| Link | 1.153 | 0.981 | **1.175 (1.113–1.240)** |
| Compass | 1.042 | 0.991 | 1.052 (1.028–1.076) |

- **The signal is there, and it's sharper with the exact heading.** The compass's ±22.5° blurs the ±30° test, as D3 expected.
- **D4's thresholds:** a lower, better-aligned sun gives a stronger signal (link headings, fine ÷ rain):
  - 15°, ±30° (the agreed rule): 1.17
  - 15°, ±20°: 1.22
  - 10°, ±30°: 1.25
  - 10°, ±20°: 1.32
  - 5°, ±15°: 1.42

  This dose-response is good evidence that the bands measure glare. The agreed rule is the widest net. Whether to tighten it is your call, as D4 said. I've kept it.

**Next: C2** (Terrain 50 and gradient), then **C3** (the filters, record panel, site rows and About page). Until C3, nothing in the app shows the new tables.
