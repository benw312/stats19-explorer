# PLAN-005 — Hotspot sites (PLAN-004 phase 4.5)

**Status:** DONE (2026-10-05) · **Branch:** `feat/4.5-hotspots` · **Parent:** PLAN-004 §4 "Area and hotspot page", decisions D5/D6

## 1. Goal

From the current selection (an authority, a drawn area or a radius; a period; any filters, e.g. "wet + dark"):

- **find cluster sites**;
- **rank** them;
- let the engineer **review a site**: map, stick diagram, year trend, and what is *over-represented* at the site compared with the wider area;
- **export** a site pack PDF and a CSV of sites.

All of this uses recorded STATS19 fields only. There are no derived collision types (FU-001 WONTFIX).

## 2. Method: greedy cluster circles (a change from PLAN-004)

PLAN-004 proposed `ST_ClusterDBSCAN`, splitting long clusters with k-means. I'm replacing it with greedy circles:

1. **Candidates:** every collision in the selection is a candidate centre. Its circle has the **cluster radius** for its own `urban_or_rural_area`: 50 m urban, 100 m rural. Unallocated or missing counts as urban.
2. **Score** each candidate circle's collisions. Score methods:
   - **KSI-weighted** (default): slight = 1, fatal/serious = 3;
   - **collisions**: a plain count;
   - **value of prevention**: DfT RAS4001 per-collision values by severity, latest year.
3. **Pick the best circle** as a site. Its collisions are then used up; they can't belong to another site. Repeat until no remaining circle qualifies or `max_sites` is reached.
   - Ties break on KSI, then collision count, then collision index, so a run is deterministic.
4. A circle **qualifies** if it has at least the minimum collisions (default 5) **or** at least the minimum KSI (default 2). These are the D5 defaults, and all of them are adjustable.

Why not DBSCAN:
- **A site is a circle of known size by construction** (≤ 100 m across urban, ≤ 200 m rural). That matches how engineers describe cluster sites ("5 collisions within 50 m"), and it can be stated on a report.
- Corridors can't chain into one long "site", so the k-means split isn't needed.
- It is deterministic and easy to explain.

**Implementation:**
- One SQL query fetches the selection's points in BNG metres; the neighbour search (a grid hash) and the greedy pick run in Python.
- A database self-join was tested and dropped: Kent over 5 years took 41 s, because the materialised CTE has no index.
- The selection query took 77 ms for Kent over 5 years (15,914 collisions).
- Target: a county over 5 years in < 10 s. Input is capped at 100,000 collisions (413 above that).
- **Cache:** results are cached in-process for 15 minutes, keyed on the filter and parameters.

**Site labels:**
- the most common STATS19 road references at the site, e.g. "A377 / B3212";
- "near <nearest OS Open Names road>, <town>".
- The nearest-road lookup needs a new GIST index on `geo.place.bbox_bng`: migration `003`, plus the reference refresh's index list.
- It is labelled "near" because Open Names gives one representative point per road, so the match is approximate.

## 3. Over-representation ("what's different here?")

`GET /api/compare?f=<site>&base=<area>` takes two filters. For each indicator it returns the count / applicable count and the share, for both the site and the area.

**Indicators.** Each one is a recorded field or a simple combination of recorded fields:

| Group | Indicators |
|---|---|
| Severity | KSI |
| Light | dark; dark without street lighting |
| Surface | wet or damp; snow, frost or ice |
| Weather | rain, snow or fog; high winds |
| Location | at a junction other than a roundabout (since the 2024 recoding, roundabouts are a road type, not a junction detail); roundabout |
| Time | weekend; 07–10 peak; 16–19 peak; night (22–06) |
| Road users | pedestrian casualty; pedal cycle; motorcycle; HGV |
| Vehicles | single-vehicle collision; a vehicle turning or waiting to turn right; turning left; slowing, stopping or waiting; skidded, jack-knifed or overturned; left the carriageway |
| People | driver aged 17–24; driver aged 70+; child casualty (< 16) |

- **Applicable count:** unknown or missing values are left out of both the numerator and the denominator. For example, "dark" is counted only over collisions with a known light condition.
- **"Notable" flag:** set when the site count is ≥ 2 and a one-sided exact binomial test against the area share gives p < 0.05. The UI says "unlikely to be chance" and always shows the counts.
- **Filter change:** the filter gains `collision_ids` (max 1,000), so a site is just a filter. Summary, sticks, list, export and the area report all work on a site unchanged.

## 4. API

| Endpoint | Purpose |
|---|---|
| `GET /api/hotspots?f=&p=` | Ranked sites + the parameters used + the selection size. `p` = `{radius_urban_m, radius_rural_m, min_collisions, min_ksi, score, max_sites}` |
| `GET /api/hotspots.csv?f=&p=` | The same, as CSV (rank, label, centre, radius, counts, score, value, ids) |
| `GET /api/compare?f=&base=` | Over-representation indicators |
| `GET /api/reports/sites.pdf?f=&p=&top=&title=&notes=` | Site pack PDF (top N sites, default 10, max 25) |

## 5. Frontend

- **Hotspots panel.** A new header toggle opens the panel.
  - It needs an area. Without one, it points to **01 Area**.
  - **Parameter block:** urban/rural radius, minimum collisions / KSI, score method, period shown with a "latest 5 years" shortcut. URL-synced (`hs=`).
  - **Ranked site list:** rank, label, F/S/s, KSI, score, and a year sparkline.
  - Hovering a site highlights it on the map; clicking opens the review.
- **Map.** Numbered site circles, with the selected site emphasised. Clicking a circle opens its review.
- **Site review:**
  - headline tiles;
  - "What's different here" over-representation bars (site vs area, flagged when notable);
  - year columns;
  - stick diagram (the existing component);
  - vehicle and casualty mix;
  - collision list;
  - PDF (single site) and site pack / CSV actions.
- **Site pack PDF:**
  - **Cover:** title, notes, parameters, and an area map with numbered sites.
  - **Ranked table** of sites.
  - **Per site:** map, figures, over-representation table, year trend, stick diagram. Ends with the key and caveats.
  - **Map snapshots:** each print map is rendered one at a time and replaced by a PNG snapshot. Chromium keeps only ~16 live WebGL contexts, and a 25-site pack needs 26 maps.

## 6. Tests

- **Algorithm unit tests** (pure Python, no DB):
  - two tight groups 30 m apart in an urban area become two sites; 120 m apart in a rural area, one site;
  - a 2 km corridor of evenly spaced collisions becomes several sites, none wider than 2 × radius;
  - KSI qualification;
  - each score method;
  - deterministic ties;
  - points already used aren't reused.
- Binomial test values against known results.
- API contract tests on the PostGIS fixture: hotspots, CSV, compare, `collision_ids` filter, size limits, the sites PDF route.
- Frontend: params URL round-trip and site helpers (Vitest).
- Browser flow and container PDF checks, as in 4.4.

## 7. Risks

- **MEDIUM — method acceptance.** Mitigation: the parameters and method are printed on every pack and are adjustable, and the greedy circle is easy to explain.
- **LOW — label accuracy** ("near …"). Mitigation: STATS19 road numbers come first; the place name is marked as approximate.
- **LOW — multiple testing in over-representation** (about 25 indicators per site, so roughly one false flag per site at p < 0.05). Mitigation: the wording is "worth a look", not "cause", and counts are always shown. A caveat is printed.
