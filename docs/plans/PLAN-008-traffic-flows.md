# PLAN-008 — Traffic flows module, then collision rates

- **Status:** T1 DONE (2026-10-06); T2 DONE (2026-10-07, awaiting review); T3–T4 DRAFT
- **Branch:** `feat/008-traffic-flows` (T1)
- **Expands:** PLAN-007 B1. This plan replaces B1's "How it's built" section after the research below.
- **Your steer (2026-10-06):**
  - build traffic flows as a module in its own right first, then integrate with collisions;
  - a map layer plus a Traffic tab;
  - OS Open Roads is fine if needed;
  - use all minor-road counts, but flag how reliable each one is.

## 1. Your questions, answered

### Q1. Can minor-road spot counts stand in for the link, using the road name and coordinates?

**Yes, as an approximation, and it's close to what DfT does internally.** The research changes one detail: the road name.

- DfT counts a sample of minor-road sites. Each count gives an AADF **for that site** (DfT methodology note). DfT doesn't define a link for minor roads, so the AADF file has **no link length** for them and `start/end_junction_road_name` is `NA`.
- **C and unclassified count points have no street name.** `road_name` is just `"C"` or `"U"` (108k of the rows). B roads do carry their number (e.g. `B1077`). So the street name has to come from the road network: snap the count point to the nearest OS Open Roads link and take that link's `name1` / `roadClassificationNumber`.
- Your "semi-accurate even with side roads" idea becomes a defined **stretch**:
  - start from the snapped OS link;
  - extend both ways along the same road (same name or number) through each junction;
  - stop where the road meets one of equal or higher class, where the name changes, or at about 2 km;
  - the stretch inherits the count point's AADF.
  - That's the same rule DfT uses to cut major roads into links ("between major junctions"), applied one level down.
- **Reliability is the real limit:**
  - Of 24,785 minor count points ever published, only **4,191** were last counted in 2020 or later. 10,705 were last counted in 2010–19 and 9,852 before 2010.
  - Only 4,393 appear in the 2025 file at all.
  - Minor flows are low (median 1,377 vehicles/day; 10% are under 162), and flow estimates are least accurate at low volumes. The literature reports errors of 190–410% under 1,000 vehicles/day ([Open Road Risk literature review](https://openroadrisk.org/literature/exposure-and-traffic-volume.html)).
  - So minor-road figures are labelled **indicative**, with the year last counted. Your answer: use all of them, flagged.

### Q2. Do we need a network model of links and nodes?

**For the traffic module (T1): no.** For proper rates: **yes for minor roads and junctions, optional for major roads.**

- **Major roads — DfT already gives the links.**
  - The **Major Road Database (MRDB)** shapefile, one per year 2018–2025, has **one line per AADF link, keyed by count point**. The 2025 file has 17,941 links, exactly matching the 17,941 major count points in the 2025 AADF.
  - The geometry is schematic: a straight line from the start junction to the end junction. Real road shape needs OS Open Roads, but the **link extents** come straight from DfT.
- **Minor roads and junctions:** collisions on C and U roads have **no road number** in STATS19, and minor stretches don't exist until we build them (Q1). Junctions need nodes. Both need OS Open Roads (OGL, 606 MB shapefile / 1 GB GeoPackage).
- **What best practice uses:**
  - DfT's own **[STATS19 network matching feasibility study](https://www.gov.uk/government/statistics/matching-stats19-collision-data-to-a-road-network-feasibility/matching-stats19-collisions-to-a-road-network-feasibility)** (24 Sept 2026) matches every collision to a network link.
  - The **EuroRAP / Road Safety Foundation risk maps** assign collisions and flows to sections of the same numbered road between meaningful junctions ([RSF protocols](https://roadsafetyfoundation.org/?p=199)).
  - The open-source **[open-road-risk](https://github.com/ThomasHSimm/open-road-risk)** (MIT) snaps collisions to OS Open Roads at a 99.8% rate.
  - So: network-based, with a confidence score on every match.

### Q3. How do collisions get linked to the flow data?

Two steps. **Collision → link** (by location plus road attributes), then **link → flow** (from the AADF).

- **Best practice: DfT's feasibility method.**
  - Candidate links within 25 m of the collision.
  - Score each candidate on: distance; **road number** (exact, or a near match allowing for typos); **road class** (police vs OS); and **form of way** (roundabout / dual / slip).
  - Pick the top score and keep the score with the match.
  - DfT's results on 2025 data: 99% matched; 93% "good" where the score is ≥ 100; 90% good overall. They plan to publish link IDs with STATS19 from summer 2027.
  - This uses OS NGD, which isn't open. **We'd copy the method on OS Open Roads**, which has the same fields.
- **The quick version, tested tonight:** major roads only, no OS. For each collision on an M or A road, take the **nearest MRDB link carrying the same road number**.
  - On 2021–25 data (242,499 collisions on M/A roads), **99.9%** have a road number that exists in the MRDB. The whole match took 4 s.
  - **Distance** to the schematic line: 48% within 50 m, 81% within 250 m. It's large on curving links because the line is straight, but that hardly matters because the road number does the work.
  - **Ambiguity:** 13% have a second same-road link within 25 m of the first. These are mostly collisions *at* the junction between two links, which should be counted as junction collisions anyway.
  - **Sanity check, collisions per 100 M vehicle-km:** trunk motorways **3.0**, trunk A **6.4**, principal A **25.5**. That's the expected order, with urban principal roads highest.
  - So **major-road link rates are possible before OS Open Roads exists**. OS then adds real shapes, junctions and minor roads, and lets us check the quick method against the full one.

### Q4. Should traffic be a standalone module first?

**Yes.**
- It's useful on its own: flows and trends, HGV share, cycling flows, a count-point card on the map.
- It's the same data B1 needs, so building it first means the loading, refreshing and UI are tested before any rate calculations depend on them.
- It needs no network, so it can ship tonight (T1).

## 2. Data (all OGL)

| Data | Use | Notes |
|---|---|---|
| `dft_traffic_counts_aadf.zip` (19 MB) | AADF per count point per year, 2000–2025, by vehicle type | 600k rows, 46,754 count points |
| `count_points.zip` | One row per count point: road, category, junction names, location, link length | Latest attributes |
| `mrdb-YYYY.zip` (0.6 MB each) | Major-road link extents for each year, keyed by count point | Straight lines, BNG. Years 2018–2025. |
| `local_authority_traffic.csv` | Vehicle miles per year by local authority, 1993–2025 (all roads) | Area rates (PLAN-007 B4) |
| OS Open Roads (T2) | Real geometry, nodes, names, form of way | 606 MB shapefile |

## 3. Phases

### T1 — Traffic flows module (no network) — tonight

- **Data:**
  - Load `geo.traffic_count_point` (latest attributes plus point geometry, and the MRDB link line for major roads).
  - Load `geo.traffic_aadf` (count point × year × vehicle types, estimation method).
  - Load `geo.traffic_la` (authority vehicle miles by year).
  - Refreshed with the other reference data: `refresh-reference traffic`.
- **API:**
  - `GET /api/traffic/tiles/{z}/{x}/{y}.mvt`: count points with the latest AADF, road type, counted/estimated and year last counted; major-road link lines when zoomed in.
  - `GET /api/traffic/points/{id}`: the count point card, with the year series by vehicle type, link extent, estimation method each year and reliability.
  - `GET /api/traffic/summary?f=`: for the current area, count points in it ranked by flow, and for an authority the vehicle-miles trend.
- **UI:**
  - **"Traffic flows" layer toggle**: points sized and coloured by AADF; minor and stale counts are hollow and greyed.
  - **Traffic tab** in the sheet: area summary and the top count points.
  - **Count-point card**: AADF trend chart (counted years solid, estimated years hollow), vehicle mix, HGV % and cycles, link "A38: B3212 → A30 (2.1 km)", a reliability badge, and a link to the DfT count point page.
- **Reliability badge:**
  - *Counted (year)*;
  - *Estimated from (year) count*;
  - *Minor road: indicative* (stale if last counted more than 5 years before the latest year).
- **Tests:** parsers (AADF, count points, MRDB shapefile, LA traffic) on small fixtures; the loader on the test database; endpoints; frontend unit tests for the reliability logic and the card.

### T2 — Road network and stretches (OS Open Roads)

- **Load OS Open Roads** `RoadLink` and `RoadNode` into `geo` with the annual refresh (adds a few GB).
- **Major links:** each MRDB link takes the OS links of the **same road number** whose midpoints lie along its straight line (projected position 0–1, within a corridor). That gives real geometry without needing routing software.
- **Minor stretches** (Q1):
  - snap each minor count point to an OS link (a B road must match its number; C/U take the nearest within 30 m);
  - grow the stretch through nodes using the stopping rules above;
  - stretches that overlap are split at the midpoint between the two count points.
- **Checks:**
  - MRDB lengths vs DfT `link_length_km`. Today the straight line is 93% of the stated length (median); the OS geometry should come out at about 100%.
  - The share of minor count points with a stretch.
  - A manual sample.

### T3 — Matching collisions to the network

Split in two: **T3a junctions** (built: §8) and **T3b links** (built: §9).

- **Method (T3b):** DfT's feasibility scoring on OS Open Roads (25 m candidates; distance + road number + class + form of way), keeping the score.
- **Junction collisions** (T3a) go to junctions we assemble from OS Open Roads (§8), not to single nodes.
- **Checks:** compare with tonight's quick major-road method and report the agreement rate; manually sample by score band, as DfT did; aim for ≥ 99% matched with low-score matches flagged.
- **Store:** a `mart.collision_link` table (collision, link or node, score, method). It's rebuilt after each STATS19 load.

### T4 — Rates, peer groups and Empirical Bayes

- This is PLAN-007 B1 from "Rates" onwards: link and junction rates, peer groups, negative-binomial safety performance functions, EB excess, the risk layer, cards and reports.
- **Model choice:** start with **negative binomial with a flow term** (not a fixed rate). Collisions rarely scale 1:1 with flow; the coefficient on flow is typically 0.6–0.9 on rural roads, and above 1 on busy motorways. That's why raw rates favour quiet roads, and why EB is used.
- **Minor roads:** stretch rates are **indicative only**, shown with the flow's age. Authority-wide minor-road rates use `local_authority_traffic` less the major-road vehicle-km.
- **Later option:** modelled flows for every link, as open-road-risk does with gradient boosting (R² ≈ 0.8). It's worth it only if the stretches leave big gaps.

## 4. Risks

| Risk | Mitigation |
|---|---|
| Minor flows are old or low-accuracy | Reliability badges; minor rates are indicative; never ranked against major roads |
| Schematic MRDB lines mislead on the map | Shown only when zoomed in, as dashed "link extent" lines; real shapes arrive in T2 |
| Count points move or are renumbered between years | Join by count point ID per year; MRDB is loaded per year in T2 |
| OS Open Roads size or refresh time | Load into `__new` then swap (existing pattern); a yearly refresh is enough |
| DfT later publishes official link IDs (from 2027) | Adopt them when published; T3 would be superseded for new years |

## 5. Status

| Phase | Status |
|---|---|
| T1 — traffic module | DONE 2026-10-06 (as built: §6) |
| T2 — network | DONE 2026-10-07 (as built: §7) |
| T3a — junctions | DONE 2026-10-07 (as built: §8) |
| T3b — link matching | DONE 2026-10-07 (as built: §9) |
| T4 — peer groups, SPFs, EB | DONE 2026-10-07 (design and as built: §10–11) |
| T4+ — regions, risk layer, value and FYRR | DONE 2026-10-07 (as built: §12) |

## 6. T1 as built (2026-10-06)

- **Load:** `stats19 refresh-reference --dataset traffic` takes about 15 s.
  - 46,754 count points; 600,551 AADF rows (2000–2025); 6,767 authority-years.
  - MRDB 2025 links attached to all 17,941 current major count points.
  - About 126 MB in PostGIS.
  - It tries the MRDB for the latest AADF year first, then up to 3 years earlier.
  - The shapefile is read with a small built-in reader, so there's no GDAL dependency.
- **Quality split:**

  | | counted latest year | recent count | old / no count | no longer published |
  |---|---|---|---|---|
  | Major | 4,241 | 8,203 | 5,497 | 4,028 |
  | Minor | 3,709 | 476 | 208 | 20,392 |

- **Authority traffic:** 205 of 207 DfT authority codes match our highway authority boundaries.
- **Tiles:**
  - below z7, strategic roads only (TM/PM/TA); z7, all major; from z8, current minor too; from z10, historic points and MRDB links;
  - the densest tile (z7 over the South East) is 169 kB raw, 73 kB gzipped;
  - minimal properties (id, aadf, type, quality); the card fetches the detail.
- **Area summary:** 25 ms for Kent, 75 ms for GB.
- **Caddy:** found that vector tiles (collision tiles too) weren't compressed, because Caddy's default `encode` list omits `application/vnd.mapbox-vector-tile`. Added it.
- **Colour:** traffic is plum `#8a2c99` (`--traffic`). The dataviz validator shows no fourth hue fully clears CVD separation against the three severity colours, so traffic uses shape (rings and dashed links, never filled dots) and collisions dim while the layer is on.
- **Also fixed:** a shared link's `#map=` view was overwritten on load. In development, StrictMode's double mount removed the first map and its hash. The hash is now read once when the map chunk loads.
- **Tests:** 10 parser tests, 2 loader integration tests, 14 API tests, 15 frontend tests. Coverage: 100% `reference/traffic.py`, 98% `api/traffic.py`.

## 7. T2 as built (2026-10-07)

**Load.** `refresh-reference --dataset road_network`:
- downloads the 1 GB GeoPackage, unpacks it (2.1 GB) and reads it with `sqlite3`, turning GeoPackage geometry into EWKB itself (no GDAL);
- **3,961,077 links and 3,346,499 nodes in 47 s**, about 2.7 GB in PostGIS; fictitious links are skipped;
- the unpacked file is deleted after the load.

**Traffic links** (`geo.traffic_link`, `geo.traffic_stretch`, dataset `traffic_links`) are rebuilt after either the road network or traffic reloads: about 70 s, 41.5 k count points.

**Major links** (DfT MRDB straight line → OS roads):
- **Candidates:** OS links with the same road number within a corridor of max(150 m, 25% of the line), excluding slip roads and roundabouts (they belong to junctions).
  - DfT `M6(T)` = OS `M6 TOLL`, the only naming difference found.
- **Cut:** each OS link keeps the part between its points nearest DfT's two junctions. Long OS links (common on motorways) are shared between count points, so `traffic_link` stores `frac_from`/`frac_to` along each link.
- **Overlaps:** found where consecutive DfT lines don't end at the same point, or a road curves back. Each OS link is split at every piece boundary, and each sub-interval goes to the count point whose DfT line is nearest (measured at the piece). Ties, where DfT lines coincide (one-way pairs, a main road and its slip road), go to the count point physically nearest. **Result: no overlapping pieces.**
- **Matched:** 17,621 of 17,941 current major links (98.2%). The rest keep DfT's straight line on the map (`kind = schematic`).
- **Length vs DfT's published length** (DfT rounds to 0.1 km, which alone puts very short links outside ±20%):

  | DfT link length | links | median ratio | within ±20% | over 150% | under 60% |
  |---|---|---|---|---|---|
  | < 0.5 km | 3,155 | 0.95 | 62% | 4.3% | 9.6% |
  | 0.5–2 km | 7,505 | 0.96 | 81% | 0.7% | 5.8% |
  | ≥ 2 km | 7,281 | 0.98 | **94%** | 0.0% | 1.6% |

**Iterations that didn't work** (for the record):
- Assigning whole OS links by their midpoint missed 1,239 trunk-motorway links whose OS links are longer than the DfT link.
- Keeping link ends that project inside the DfT line left 15,000 overlapping pieces.
- "Contained piece goes to the nearer line" dropped whole short links.

**Minor stretches:**
- **Snap:** within 30 m to the expected OS class (B count points must match their number; C → Classified Unnumbered first; U → Unclassified first).
- **Grow** (`reference/stretch.py`, unit-tested on hand-built networks): continue along the same road (same number; else same name; unnamed roads only through simple joins), stopping at a junction with an equal or higher class road, a road end, or 1 km each way.
- **Overlaps:** each link goes to one count point; current counts beat historic ones, then the nearest.
- **Result:** 4,389 of 4,393 current minor points (99.9%) and 19,531 of 20,392 historic ones. Median snap 1 m; median stretch 339 m, 90% under 1.9 km.

**Map and card:**
- **Map:** from z9, major links drawn solid on the real roads; from z12, minor stretches dashed (indicative); unmatched major links as faint dots on DfT's straight line. The open count point's road gets an ink casing. Line geometry is simplified to the tile's pixel size, so the densest tile (London, z9) is 87 kB gzipped.
- **Card:** an "Applies to" line, e.g. "1.43 km of road between DfT's junctions (DfT: 1.4 km)" or "About 522 m of Nurstead Lane, until a junction with an equal or bigger road (indicative)". C and U count points take their OS street name ("Nurstead Lane (unclassified road)").

**Known limitations:** see FU-034.

**Tests:**
- 7 stretch-rule tests, 14 link-matching unit tests and 6 GeoPackage conversion tests;
- loader and link-building integration tests on a hand-built GeoPackage around the fixture count points;
- 5 new API tests and 5 new frontend tests.
- Coverage of the new modules: 96%.

## 8. T3a junctions as built (2026-10-07)

**Why we build junctions.** OS Open Roads names only motorway junctions (669, e.g. "M5 J30"). Its nodes aren't junctions either:
- a dual carriageway or staggered junction is several nodes;
- a roundabout is a ring of links;
- some "junction" nodes are only a carriageway splitting.

So we assemble junctions the way COBALT and the Highway Safety Manual (HSM) treat them (`reference/junctions.py`, rules unit-tested; `reference/junction_build.py`).

**Rules.**
- **Junction nodes:** where three or more public-road links meet, plus every roundabout ring node and mini-roundabouts (OS "roundabout" nodes that aren't on a ring).
  - Private and car-park access links are left out, so a car park entrance doesn't make a junction. These are OS road functions "Restricted Local Access Road" and "Secondary Access Road".
- **One junction:** all of a roundabout ring's nodes, plus nodes joined by a link of 30 m or less (dual carriageway crossings, staggers). The shortest links join first, and a junction can't span more than 60 m (or the ring plus 30 m each side), so a street of close junctions doesn't chain into one.
- **Arms:** the links leaving the junction, grouped by road identity (number, else name) and direction (within 60°).
  - The two carriageways of a dual road are one arm; the two sides of a through road are two arms.
  - Car-park accesses aren't arms.
- **Type:**
  - roundabout, mini-roundabout, T or Y (3 arms), crossroads (4 arms), more than four arms (5+).
  - Fewer than three arms isn't a junction: a carriageway split or a turning circle.
  - Merges and diverges stay with the link, as COBALT does: a slip road joining or leaving a motorway or dual carriageway where every other arm is that road. The junction is where the slip road ends.
- **Names:** the roads that meet, biggest first ("A38 / B3212 / Mill Lane"). A junction with a slip-road arm within 750 m of an OS motorway junction point takes its number.
- **Signals** (OpenStreetMap `highway=traffic_signals`, Geofabrik's GB extract read with pyosmium in about 5 s):
  - signals tagged as pedestrian crossings are excluded;
  - a junction is signalised if a signal is on the junction itself (5 m), or signals within 30 m sit on approaches at least 60° apart;
  - one or two signals on a single arm are more likely a pedestrian crossing near a priority junction.
- **Motorway junction numbers:** 550 of the 669 OS numbers land on at least one junction (1,187 junctions, e.g. M5 J30 Sandygate: a signalised 10-arm roundabout).
- **Slip roads splitting or joining each other** inside an interchange are diverges, not junctions.
- **Ids:** the smallest OS node id in the junction, so links survive rebuilds while OS keeps its ids.

**Which collisions are junction collisions.** STATS19 records "at or within 20 m of a junction". The 2024 coding (`junction_detail` 13–19) has **no roundabout, mini-roundabout or slip road values**: since 2024, and in the back-filled field for every year, those collisions are coded 0 ("not at junction"). We therefore count a collision as a junction collision if any of these hold:
- historic detail 1–9;
- new detail 13–19;
- road type = roundabout (consistent at about 6k a year);
- any recorded junction control.

Each one from the last 10 years goes to the nearest junction within **25 m**: STATS19's 20 m plus location error, as in DfT's feasibility study. For roundabouts the distance is measured to the ring.

**Exposure (COBALT, HSM).** Vehicles **entering**: half of each counted arm's two-way AADF.
- Both sides of a through road are separate arms sharing one count, so the main road counts once in full.
- The major-road and minor-road parts are kept apart: most side roads have no count.
- A rate (collisions per million vehicles entering) is given when every major arm is counted. When minor arms are uncounted it's flagged as reading high.

**GB results** (OS Open Roads 2026-10; about 2.5 minutes to build, 1.4 GB in PostGIS):

| Type | Junctions | Signalised (OSM) |
|---|---|---|
| T or Y | 845,902 | 6,524 |
| Crossroads | 161,325 | 7,346 |
| More than four arms | 20,075 | 1,771 |
| Roundabout | 11,648 | 998 |
| Mini-roundabout | 6,247 | 17 |

- **Matched:** 531k of the 641k junction collisions in the last 10 years (83%).
  - The rest are mostly "private drive" (26% matched: OS doesn't map most drives) and slip-road collisions (41%: merges stay with links, by design).
  - Without those two, 88%.
- **Agreement with how police recorded the junction** (collisions 2016+):

  | STATS19 says | matched | our type |
  |---|---|---|
  | T or staggered | 86% | 68% T, 25% crossroads (STATS19 lumps staggers in with T) |
  | Crossroads | 92% | 79% crossroads |
  | Roundabout | 90% | 69% roundabout + 10% mini |
  | Mini-roundabout | 87% | only 6% mini: OS doesn't mark most minis, so they're typed by arms |

- **Signals vs police-recorded control** (matched collisions):
  - recorded as signals: we mark signalised 77% (roundabouts 90%);
  - recorded as give way: we mark signalised 3.3%.
  - Counting any signal within 30 m would raise the first to 86% but the second to 8.3%, mislabelling give-way junctions, so the stricter rule stays.
  - The card also shows what police recorded at the junction's collisions, as a cross-check.

**Map and card.**
- **Map:** junctions from z13 (motorway/A/B), z14 (+C) and z15 (all), as ink rings sized by the junction collisions matching the current filters. Collision points draw on top and win the click.
- **Card** (`?jn=<id>`):
  - type, arms, control and motorway junction number;
  - collisions in the period, by severity and year (default: the last 5 years, or the filter's years);
  - the rate per million vehicles entering, with coverage;
  - each arm's road, direction and DfT count (click through to the count point);
  - police-recorded control.

**Update (2026-10-07, accuracy pass):**
- **Mini-roundabouts from OSM:** the OSM read now also takes `highway=mini_roundabout` (15,174 in GB, against about 6k marked by OS). A junction typed by its arms (T, crossroads, multi-arm) with one within 15 m becomes a mini-roundabout; `arm_kind` keeps the arm-based type.
  - GB: 17,155 mini-roundabouts (was 6,247).
  - Of collisions police recorded at a mini-roundabout, 85% now sit at one of ours (was 6%). Under 1% of police T and crossroads collisions land on one.
  - 18% of police "roundabout" collisions are at an OSM mini, which suggests police often record minis as roundabouts.
- **Dataset rename:** the OSM dataset is now `osm_nodes` (table `geo.osm_node`, kinds `signals`, `crossing_signals`, `mini_roundabout`). Reloading it re-marks signals and minis in place, or rebuilds the junctions if the table predates `arm_kind`.

**Next (T4):** typical flows for uncounted minor arms (DfT minor-road sample medians by class and urban/rural), peer groups (type × control × speed limit × urban/rural × flow band), safety performance functions and EB excess.

**Tests:**
- 19 rule tests (clustering, arms, types, names, roles);
- 8 signals parser tests (a PBF written with pyosmium);
- integration tests on the fixture network, now with a roundabout, an M5 slip road, a car park access and a motorway junction point: types, names, signals, arms with count points, and collision matching across both STATS19 codings and the time window;
- 12 API tests and 15 frontend tests.

**Build note:** each junction row is written once, geometry and flags included. An earlier version updated the million rows afterwards (geometry, then signals), and those rewrites left the table at 1.5 GB instead of 0.4 GB.

## 9. T3b link matching as built (2026-10-07)

**Method** (`reference/collision_links.py` rules, unit-tested; `reference/collision_link_build.py`). We follow DfT's 2026 feasibility study:
- **Candidates:** every OS link within 25 m of the collision.
- **Score** (DfT publishes the components but not the weights; ours put a close match on the right road number and class at 100+):

  | Component | Points |
  |---|---|
  | Distance | up to 50, quadratic, 0 at 25 m (police locations sit 5–10 m off OS's centreline on dual carriageways) |
  | Road number: exact (incl. M6 → M6 TOLL) | +40 |
  | Road number: one edit apart, same letter (a likely typo) | +15 |
  | Road number: police recorded none (C/U) and the link has none | +35 |
  | Road number: police recorded none but the link has one | −10 |
  | Road number: wrong | −20 |
  | Road class agrees (police M / A(M) / A / B / C / U vs OS class) | +15 |
  | Form of way agrees (roundabout, dual, single, slip) | +15 |
  | A slip road or roundabout link when police recorded neither | −10 |

- **Pick:** best score, then nearest, then link id. The score, distance, position along the link and margin over the runner-up are kept.
- **Scope:** collisions of the last 10 years, re-matched after each STATS19 load and each road network refresh (45 s for GB).
- **Which count point:** a collision takes the count point whose link piece covers its position. This is looked up at query time, so a traffic reload needs no re-match.
- **Junctions:** collisions on roundabout rings and slip roads belong to junctions, never links. Collisions also assigned to a junction on the link (e.g. a T-junction along an A road) stay on the link, as in EuroRAP's risk maps, and are counted separately.

**GB results** (2016–2025):
- **Matched:** 1,101,292 of 1,111,598 located collisions (99.1%; DfT 99%).
- **Score bands:** 81% scored 100+, 15% scored 75–99, and 3.9% scored under 75 (flagged; DfT reports about 1% under 75 with its NGD network).

  | Police road class | 100+ | 75–99 | under 75 | road number agrees |
  |---|---|---|---|---|
  | Motorway | 83% | 15% | 3% | 97.9% |
  | A(M) | 82% | 12% | 6% | 94.8% |
  | A | 89% | 6% | 5% | 97.3% |
  | B | 92% | 4% | 5% | 97.8% |
  | C | 60% | 37% | 3% | (unnumbered) |
  | Unclassified | 70% | 27% | 3% | (unnumbered) |

  C roads score lowest because police "C" and OS "Classified Unnumbered" often disagree.
- **Flow:** 87% of M and A road collisions (2021–25) land on a traced DfT link. The rest are on roundabout rings, slip roads, junction nodes or unmatched links. Of those, the count point's road matches the police road number for 98.7% (A), 99.1% (M) and 96.8% (A(M)).
- **Link rates, 2021–25** (collisions per 100 million vehicle-km):

  | Road category | All along the road | Between junctions | Quick straight-line method (Q3) |
  |---|---|---|---|
  | Trunk motorway | 2.5 | 2.5 | 3.0 |
  | Trunk A | 5.5 | 4.5 | 6.4 |
  | Principal A | 23.9 | 12.0 | 25.5 |

  The order is as expected, and the rates are slightly lower than the quick method's, because ring and slip-road collisions now go to junctions.

**Card.** The count-point card gains "Collisions on this road":
- collisions in the period (filters apply), by severity and year, with how many were at junctions along it;
- the rate per 100 million vehicle-km (all along the road, and between junctions), from our traced length and the period's mean AADF;
- a count of low-confidence matches. Minor roads are labelled indicative.

**Tests:** 17 scoring unit tests; an integration test of matching on the fixture network (exact number, unnumbered-to-unnumbered, out of range, out of window); an API test of the card's counts and rate.

**Next (T4):** peer groups for links (road category × urban/rural × carriageway × flow band) and junctions, safety performance functions, EB excess, and a risk layer on the map.

## 10. T4 design: peer groups, safety performance functions, Empirical Bayes (2026-10-07)

**Aim.** Answer "is this road or junction worse than similar ones, given its traffic?", which is what an engineer needs before spending money. Raw rates mislead in two ways: collisions don't scale 1:1 with flow, and a few collisions in a short window are mostly chance. The standard answer (HSM Part B, used in UK practice and in EuroRAP's star ratings research) is:
1. fit a **safety performance function** (SPF) per peer group: negative binomial regression of collisions on flow;
2. combine each site's prediction with its own count by **Empirical Bayes** (EB);
3. rank by **excess**: EB-expected minus predicted collisions.

**Units and period:** the last 5 years of collision data.
- **Links:** current major count points with a traced OS link.
  - Collisions: those on the link that are *not* junction collisions, so links and junctions don't double count.
  - Exposure: traced length × mean AADF over the period.
- **Junctions:** junctions whose major arms are all counted.
  - Collisions: matched junction collisions.
  - Exposure: vehicles entering, with a flag when minor arms are uncounted.

**Peer groups** (from open data only):
- **Links:** road category (motorway / trunk A / principal A) × carriageway (dual or single, from the OS form of way along the link) × urban/rural.
- **Junctions:** type (roundabout, mini-roundabout, signalised, priority T, priority crossroads/multi-arm) × urban/rural.
- **Urban/rural:** junction density, since no open GB-wide urban flag matches roads. A site is urban when 18+ junctions lie within 500 m. Checked against the police urban/rural flag on 20k 2024 collisions: under 5 junctions, 2% urban; 30–49, 91%; 50+, 98%; crossing 50% at about 18.
- **Speed limit isn't open** (OS speed data is licensed), so it's not a grouping variable. Urban/rural carries most of the same signal.
- **Small groups:** a group of fewer than 100 sites drops its last split (carriageway, then urban/rural) and joins the broader group.

**Models** (statsmodels, NB2):
- links: log μ = b0 + log(length) + b1·log(AADF);
- junctions: log μ = b0 + b1·log(entering) + b2·[minor arms uncounted].
- One model per peer group; coefficients, α and fit statistics are stored.

**EB** (HSM 3.36): w = 1 / (1 + α·μ); EB = w·μ + (1 − w)·N; excess = EB − μ (positive = worse than similar sites). Links are also ranked by excess per km.

**Output:**
- `geo.safety_unit`: one row per link or junction, with peer group, observed, predicted, EB, excess and flows;
- `geo.safety_model`: per group, n, coefficients, α, mean observed;
- dataset `safety`, rebuilt after the collision matches, a traffic reload and each STATS19 load.

**App:**
- **Cards:** the count-point and junction cards get "Compared with similar roads/junctions":
  - predicted, observed and EB-expected collisions;
  - excess;
  - percentile within the peer group.
- **Ranked list:** an area list of the highest-excess roads and junctions (in the Traffic panel), click-through to the cards.
- **Map:** a risk layer on the map comes after this (it needs the ranked data first).

**Caveats shown in the app:**
- minor-road counts are indicative;
- junctions with uncounted minor arms carry a flag;
- excess is a screening measure (where to look), not proof of a defect;
- regression to the mean is what EB corrects for.

## 11. T4 as built (2026-10-07)

**Build** (`reference/safety.py` rules and fit, `reference/safety_build.py`): 80 s for GB.
- **Sites:** 142,700 scored, 2021–25.
  - 17,600 major links;
  - 125,100 junctions whose major arms are all counted.
- **Models:** 20 peer groups.
- **Small groups:** single-carriageway motorway links (7) are too few to model and are left unscored.
- **Fitting:** the default optimiser stalled at α = 0 for rural dual trunk A roads (variance 109 against a mean of 8, so clearly overdispersed). Fits now start from a Poisson fit plus a moment estimate of α, try Newton, BFGS and Nelder–Mead, and keep the best likelihood. That group's α went from 0 to 0.37.

**Models** (flow exponent b, overdispersion α):

| Peer group | Sites | b | α |
|---|---|---|---|
| Motorway, dual, rural / urban | 830 / 316 | 0.94 / 0.89 | 0.27 / 0.32 |
| Trunk A, dual, rural / urban | 915 / 325 | 0.92 / 0.68 | 0.37 / 0.46 |
| Trunk A, single, rural / urban | 728 / 146 | 0.77 / 1.22 | 0.30 / 0.41 |
| Principal A, dual, rural / urban | 777 / 2,171 | 0.84 / 0.62 | 0.39 / 0.72 |
| Principal A, single, rural / urban | 4,671 / 6,714 | 0.86 / 0.85 | 0.27 / 0.89 |
| Roundabout, rural / urban | 2,295 / 3,557 | 1.23 / 1.12 | 0.63 / 0.80 |
| Mini-roundabout, rural / urban | 517 / 2,492 | 0.83 / 0.88 | 0.78 / 0.94 |
| Signals, rural / urban | 919 / 8,894 | 0.58 / 0.57 | 0.89 / 0.94 |
| Priority T, rural / urban | 33,222 / 49,557 | 0.74 / 0.87 | 2.07 / 1.87 |
| Priority crossroads/multi-arm, rural / urban | 6,283 / 17,364 | 0.64 / 0.78 | 2.00 / 1.47 |

Flow exponents are 0.6–0.9 for most groups and above 1 for motorways and roundabouts, as the literature expects. Collisions rise more slowly than traffic, which is why raw rates favour quiet roads.

**Out-of-sample check.** Rank on 2016–20, then see what the top 2% did in 2021–25:

| Ranked by | Links: excess in 2021–25 | Junctions: excess in 2021–25 |
|---|---|---|
| **EB excess** | **7,924** | **15,464** |
| Raw collision count | 5,062 | 14,751 |
| Raw rate (observed ÷ predicted) | 2,910 | 6,770 |

- EB excess picks the sites that stay worse than similar ones: on links, 57% more next-period excess than ranking by counts, and 2.7× more than ranking by rates.
- Raw-rate ranking looks good on observed ÷ predicted but picks low-flow sites where the ratio is noise.

**App:**
- **Cards:** the count-point and junction cards show "Compared with similar roads/junctions":
  - expected at similar sites, observed, the EB best estimate, and the excess with its band ("in the worst 5% of 2,295");
  - the peer group in words, and the caveats.
- **Ranked list:** the Traffic panel's "Worse than similar sites" lists the junctions or roads in the area with the largest excess, which open their cards (`/api/safety/top`, 0.5 s for a county).
- **Devon, 2021–25:**
  - top junction: A30/A377/Ide Village Road roundabout, 15 observed vs 3.1 expected (+7.9);
  - top road: the A399, 28 vs 12.4 (+12.1).

**Not yet:** KSI-specific models and the remaining limitations in FU-038. The risk layer, regions and scheme economics followed (§12).

## 12. Regions, risk layer, value and FYRR as built (2026-10-07)

**Regions (a correctness fix found while building the layer).**
- Fitted nationally, 21.6% of London sites were in the worst 5%, against 0.7% in Scotland and 1.0% in Wales.
- London's mean excess was +1.7; everywhere else it was below zero.
- The cause is that police forces record collisions at very different rates for similar roads and traffic.
- **Fix:** every SPF now takes region indicators (London, Scotland, Wales; the rest of England is the baseline). This is the HSM's calibration by jurisdiction.
  - A region needs 30 sites in a group to get its own level; otherwise it shares the baseline.
- **Fitted levels** against the rest of England:
  - London ×1.2–3.8 (urban groups ×2.3–3.8, e.g. urban priority T ×3.6);
  - Scotland ×0.3–0.8;
  - Wales ×0.3–0.8.
  - Mean excess is now about 0 in every region.
- **Ranking:** absolute excess still grows with the collisions a region records, so a national rank kept favouring London (18%). Sites are now ranked among similar sites **in their own region**, giving 5.0% / 5.0% / 5.0% / 5.0% in the worst 5%.
  - The card says so: "worst 1% of 158 urban roundabouts in London".
- `geo.safety_unit.region` stores the region; `group_size` is the region's count within the group.
- The §11 out-of-sample check has not been re-run with regions (FU-038).

**Risk layer** (`/api/safety/tiles/{z}/{x}/{y}.mvt`, `components/map/riskLayers.ts`):
- Legend toggle "Worse than similar sites".
- **What it draws:** count-point roads (traced OS links) and junctions, banded by where their excess ranks: worst 1% / 5% / 20%, about as expected, best 20%.
- **Colours:** amber to dark brown for worse, grey for as expected, teal for better. Each arm passed the dataviz ordinal check, and worse bands are drawn wider and larger, so colour isn't the only cue.
- **Junctions by zoom:** worst 5% from z9, worst 20% from z13, all from z15. Roads are shown from z5.
- **Interaction:** collisions dim underneath. Clicking a road or junction opens its card, and the open site gets an outline.
- **Tiles:** 180–250 kB at z7–10 across London, 10–60 ms.

**Value of the excess** (PLAN-007 B5):
- Each group's model now carries its severity totals (`observed_total`, `ksi_total`, `fatal_total`).
- The API values one collision at the group's mix with DfT's latest RAS4001 values. A single site's own mix is too noisy, since one fatal collision multiplies it tenfold.
- **Cards:** "the excess is worth about £705k a year (+7.5 collisions a year × £94k, DfT 2025 prices)".
- **Ranked list:** each row shows £ a year.

**Scheme return (FYRR) calculator** (`components/economics/FyrrCalculator.tsx`, `lib/economics.ts`):
- **Inputs:** scheme cost (accepts "40k" or "1.2m") and the expected reduction (default 25%).
- **Outputs:** collisions saved a year, value a year, first-year rate of return, and payback.
- **Road and junction cards:** apply the reduction to the **EB best estimate** a year, so the return isn't inflated by regression to the mean.
- **Cluster-site review:** uses the site's own count and severity value, labelled as unadjusted.
- Not yet on the site PDF (FU-038).

## 13. Out-of-sample check with regions (2026-10-07, FU-038 #8)

This is now a command, `stats19 safety-check` (`reference/safety_check.py`, about 2 minutes). It scores every site on 2016–20 and on 2021–25 with the same models, picks the worst 2% of the earlier period by each method, and follows those sites into the later period.

| Sites | Method | Picked | Excess in 2021–25 | Still in the worst 20% | Picks in London |
|---|---|---|---|---|---|
| Junctions | **EB, ranked within region** (the app) | 2,303 | 4,743 | **73%** | 10% |
| | EB, ranked nationally | 2,303 | 8,634 | 73% | 58% |
| | Raw collision count | 2,303 | 7,871 | 66% | 61% |
| | Raw rate (observed ÷ predicted) | 2,303 | 1,665 | 53% | 2% |
| Roads | **EB, ranked within region** (the app) | 326 | 3,902 | **88%** | 10% |
| | EB, ranked nationally | 326 | 4,806 | 89% | 33% |
| | Raw collision count | 326 | 2,302 | 61% | 36% |
| | Raw rate | 326 | 655 | 29% | 7% |

- **Persistence is the fair test.** Ranking within region picks sites that stay worse than similar ones as reliably as national ranking: 73% vs 73% for junctions, 88% vs 89% for roads. It also spreads the picks across regions roughly in proportion: England outside London 71%, London 10%, Scotland 12%, Wales 6%.
- **Absolute excess favours London.** National ranking and raw counts accumulate more absolute next-period excess, because London records about three times the collisions of similar sites elsewhere. That's the bias regional ranking removes (§12), not extra safety benefit.
- **Raw rates are noise.** They do worst on every measure: they pick quiet sites where the ratio is unstable.
- These numbers replace §11's, which predate regional levels. §11's link figure (7,924) was national excess with national models.
