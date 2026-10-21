# PLAN-007 — Roadmap: what else would help a highways engineer

- **Status:** DRAFT 2026-10-06, for you to pick from (section 6)
- **Branch:** `docs/plan-007-roadmap`
- **Builds on:** PLAN-004 Build 2 and Build 3 (query builder, routes, before/after, collision rates), FU-026 nice-to-haves
- **Rule kept from FU-001:** recorded fields only, no inferred collision types. Every new number says where it came from and how reliable it is.

## 1. Summary

| # | Feature | Size | Value | Needs new data |
|---|---|---|---|---|
| **B1** | **Collision rates from traffic flows, and comparison with similar roads** (your idea) | L | ★★★ | DfT AADF, OS Open Roads |
| B2 | Route / corridor analysis with a strip chart along the road | M | ★★★ | OS Open Roads (shared with B1) |
| B3 | Before/after scheme monitoring, corrected for regression to the mean | L | ★★★ | none (B1 makes it much better) |
| B4 | Authority benchmarking: rates per population, per vehicle-km and per km of road, against GB and similar authorities | M | ★★ | ONS population, DfT LA traffic, DfT road lengths |
| B5 | Scheme economics: first-year rate of return (FYRR) calculator for a site | S | ★★ | none (RAS4001 already loaded) |
| B6 | Schools and children: child casualties near schools and on school-run times | S–M | ★★ | DfE school locations (GIAS) |
| B7 | Where casualties live: residence-based casualty rates by deprivation | S–M | ★ | ONS LSOA population and boundaries |
| M1–M12 | Smaller improvements (section 4) | S each | | mostly none |

**My recommended order:**
1. **M1**: severity adjustment. It's a correctness fix for trends.
2. **B1 + B2** together. Both need the road network, and B1's peer-group models are what make B3 rigorous.
3. **B3**.
4. **B5**.
5. Then B4 / B6 / B7 as you prefer.

The quick wins in section 4 can fill gaps between these.

## 2. Data I checked today

| Source | What it gives | Licence | Checked |
|---|---|---|---|
| **DfT road traffic statistics, AADF by count point** (`dft_traffic_counts_aadf.zip`, 19 MB, roadtraffic.dft.gov.uk) | Annual average daily flow by vehicle type (pedal cycles, motorcycles, cars, buses, LGVs, HGV axle classes, all motor vehicles); road name and category; start/end junction names; link length; counted vs estimated | OGL | Downloaded and profiled on 2026-10-06: years **2000–2025**, 600k rows. In 2025 there are 17,941 major-road links with lengths (51,534 km, **360 bn vehicle-km**) and 4,393 minor-road count points, **with no link lengths for minor roads**. 7,815 of 22,334 figures for 2025 are counted; the rest are estimated. |
| **DfT local authority traffic** (same site) | Vehicle-km per year by local authority, split major / minor | OGL | Not yet profiled. It's a standard download alongside the AADF file. |
| **National Highways WebTRIS API** | 15-minute flows from loop sensors on motorways and trunk roads (England only) | OGL, free, no key | API listed on [Find Transport Data](https://findtransportdata.dft.gov.uk/dataset/webtris-traffic-flow-api). Useful for hour-of-day exposure on the strategic road network (SRN) (M10). |
| **OS Open Roads** | GB road links and nodes with road number, class, form of way (single/dual/slip/roundabout), length | OGL | Already planned in PLAN-004 §3 "Later". |
| **DfT RAS tables** (e.g. RAS0302 urban/rural, RAS0303 strategic road network) | National casualty rates per billion vehicle-miles by road type, used as published benchmarks | OGL | [Data tables index](https://www.gov.uk/government/statistical-data-sets/road-safety-statistics-data-tables) |
| **ONS mid-year population estimates** (LA and LSOA) | Denominators for per-population rates | OGL | Standard ONS release |
| **DfE Get Information about Schools** | Every school in England with location, phase and pupil numbers | OGL | Standard daily extract. Scotland and Wales publish their own lists. |

**Coverage limits (these matter for B1):**
- **Major roads** (motorways and A roads) have a flow for every link. These carry about two thirds of traffic and most KSI.
- **Minor roads** only have sample count points. So link-level rates on B, C and unclassified roads aren't possible from open data. Minor roads get **area-level** rates from the LA traffic table (B4).
- **There are no open turning counts at junctions.** Junction rates use the flows on the major arms entering the junction (section 3, B1).

## 3. Big features

### B1 — Collision rates and "similar roads" comparison

> **Updated 2026-10-06:** the research and build approach are now in **[PLAN-008](PLAN-008-traffic-flows.md)**: traffic flows as a standalone module first (T1, PR #14), then the road network (T2), collision matching (T3) and rates with Empirical Bayes (T4). Changes from the text below:
> - DfT's Major Road Database already gives every major link's extent, so the "walk the network" step is unnecessary;
> - C and U count points have no street name, so they're snapped to OS Open Roads;
> - collision matching follows DfT's 2026 feasibility method.

**The engineer's question:** "This A-road link has 14 collisions in 5 years. Is that high for a road like this carrying this traffic, or just a busy road?"

**What it does:**
- **Rates on every major-road link:**
  - collisions and KSI per **100 million vehicle-km** (the standard UK measure);
  - for vulnerable users: pedal-cycle casualties per cycle-km and motorcycle casualties per motorcycle-km, using AADF's vehicle split.
- **Junction rates:** collisions per **million vehicles entering**, using the summed AADF of the major arms at the junction.
- **Peer groups ("similar scenarios"):** road class (motorway / A trunk / A principal) × urban/rural × speed limit × carriageway (single/dual, from OS Open Roads) × flow band. Junctions are grouped by type (roundabout / signals / priority, from STATS19 `junction_detail` and `junction_control` at the node) × arm count × flow band.
- **Expected vs observed:**
  - Fit a **safety performance function** for each peer group: a negative-binomial model of collisions against flow and length.
  - Combine it with the site's own history using the **Empirical Bayes** method (as in the US Highway Safety Manual, and used in UK practice) to get the **excess expected collisions**, also called potential for safety improvement.
  - This ranking corrects for regression to the mean. A raw "worst rate" list tends to favour short, quiet links with one bad year.
- **On screen:**
  - A **risk map layer** colouring links in five bands, like the EuroRAP risk maps.
  - A link or junction card: "Rate 2.3× similar roads (EB excess 3.1 collisions/yr). 95% interval 1.6–3.2×".
  - HGV over-representation: "HGVs are 9% of traffic here but in 31% of collisions".
  - A "worst links in this authority" ranked table, plus a PDF / CSV export like the site pack.

**How it's built:**
1. **Load** AADF (all years) and OS Open Roads into `geo`, with an annual refresh like the existing reference data.
2. **Link flows:**
   - The AADF major-road network is made of OS links grouped between major junctions.
   - Give each OS link with road number X the flow of the count point on X that covers it: walk the network along road X from the count point to its start/end junctions, using the junction names as a check.
   - Links that can't be matched are flagged and left without a rate rather than guessed.
3. **Collisions to links and nodes:**
   - Snap each collision to the nearest OS link **with the same road number** (`first_road_class` + `first_road_number`) within 30 m urban / 60 m rural.
   - Junction collisions (`junction_detail` ≠ not at junction) go to the nearest node within 20 m.
   - Unmatched collisions are counted and reported, never forced.
4. **Exposure:** sum AADF × 365 × length over the analysis years, using each year's flow, not just the latest.
5. **Models:** fit the safety performance functions in Python per peer group and years, and store the coefficients in a `mart.spf` table so the same models drive B3. This adds `statsmodels` or a small negative-binomial fit with `scipy`; I'd pick `statsmodels` for the tested GLM.
6. **API and UI:** a `/api/rates` endpoint (filter-aware, so "rates for wet + dark" works), the tile layer, the link/junction card, the ranked table, and the report.

**Caveats shown in the app:** an "estimated" flow badge where AADF isn't counted that year; junction flows from major arms only; minor-road collisions excluded from link rates (and said so).

**Effort:** the largest item here. About 3 PRs: data and matching; rates and models; UI and report.

### B2 — Route / corridor analysis (PLAN-004 Build 2, now concrete)

- **Selecting a route:** pick a road number and two points ("A38 from junction X to Y"), or draw a line. The app then snaps to OS Open Roads and buffers it.
- **Strip chart:** collisions plotted by chainage along the route, with severity marks and junction ticks.
- **Per-km figures:** collisions per km and, with B1, the rate per km in sections, with sections above the peer-group rate highlighted.
- **Route report PDF:** strip chart, table by section and stick diagram.

This shares B1's network and snapping code, which is why I'd build them together.

### B3 — Before/after scheme monitoring (PLAN-004 Build 3)

- **Recording a scheme:** site (a circle, polygon or route from B2), completion date, description and cost. This needs the database's first **writeable** table, `app.scheme`.
- **Comparison:** before vs after periods (default 3 years each, excluding the construction period), alongside a comparison area for the general trend. The default comparison is the rest of the authority on the same road classes.
- **Corrections:**
  - With B1's models, use the **EB-adjusted** before count, which corrects for regression to the mean. It's the main reason naive before/after results overstate scheme benefits.
  - Without B1, show the naive result with a clear warning.
- **Output:**
  - The percentage change with a confidence interval, collision and casualty savings, and money values from RAS4001.
  - A monitoring report PDF.
  - A schemes list with status ("monitoring: 14 of 36 months after").
- **Topical use:** the Wales default 20 mph change (September 2023) as an area scheme. Authorities are being asked about this now.

### B4 — Authority benchmarking

- **Rates:** for an authority, casualties and KSI per 100k population, per bn vehicle-km (split major / minor), and per 100 km of road, each year against GB and the region.
- **Similar authorities:** compare with authorities of the same ONS area classification. The usual CIPFA nearest-neighbour list isn't open data.
- **Annual summary page and PDF:** the figures most authorities put in their annual road safety report, including KSI trend vs baseline, vulnerable road users and children.

### B5 — Scheme economics (FYRR) — DONE 2026-10-07 (PLAN-008 §12)

- On a site: enter the scheme cost and the expected reduction (a % per collision type, or one overall figure).
- The app gives the annual collision saving and its value (RAS4001, by severity), the **first-year rate of return**, and payback time.
- It's printed on the site pack page.
- This is a small feature, but it's how local safety schemes get prioritised.

### B6 — Schools and children

- **School layer:** schools as a map layer from GIAS for England, plus the Scottish and Welsh lists.
- **"School journey" quick filter:** weekdays, 08:00–09:30 and 14:45–16:30, casualty age < 16. It's labelled as approximate because term dates aren't in the data.
- **Near-school view:** child pedestrian and cyclist casualties within 400 m / 800 m of each school, ranked, with a PDF.

### B7 — Where casualties live

- STATS19 records the **casualty's home LSOA** and **IMD decile**, which we don't use yet.
- **Residence map:** casualties per 1,000 residents by home LSOA, shaded by deprivation decile.
- **Children by deprivation:** child casualty rate by IMD decile, a well-known inequality measure that public health partners ask for.
- **Disclosure control:** suppress small counts (< 5) on the map.

## 4. Smaller improvements

| # | Improvement | Why |
|---|---|---|
| **M1** | **Use DfT's severity adjustment in trends.** The adjusted serious/slight figures are already in `mart.collision` but not shown. Add an "adjusted" toggle (default on for multi-year trends), with a note on the CRASH/COPA changeover. | **Correctness.** Forces moved to injury-based reporting (CRASH) in different years from 2012, which raised recorded serious injuries. Unadjusted KSI trends and before/after comparisons across that change are biased. |
| M2 | Period comparison: two periods side by side (e.g. 2016–20 vs 2021–25) for the current selection, with change and significance | Planned for Build 2. Cheap now that compare exists. |
| M3 | Saved selections and site lists, shared by URL with a name | Build 2. The first writeable table; it can share B3's `app` schema. |
| M4 | GeoJSON / GeoPackage export of collisions and cluster sites | GIS users (FU-026) |
| M5 | Casualty ↔ vehicle linking on the stick diagram (casualty X was in vehicle 2) | FU-026; the data has the reference |
| M6 | Trend significance: a Poisson test or interval on the year trend ("down 18%, 95% CI −30% to −4%") and on the summary tiles | Compare already has significance tests; trends don't |
| M7 | Speed limit as a map layer, and quick filters for the 20 mph change | Topical; the field exists |
| M8 | Area report: a cluster-sites summary section when the selection is an authority | FU-026 |
| M9 | "Find similar sites": sites where the same indicators are over-represented, e.g. other "wet + dark" clusters | FU-026; uses `/api/compare` |
| M10 | WebTRIS hour-of-day exposure for SRN links: collisions per vehicle by hour, not just counts by hour | It shows whether the night peak is risk or just traffic. England only. |
| M11 | Data-quality flags in the record card: police attended or self-reported, location adjusted, `*_historic` recoded | Helps engineers judge single records |
| M12 | Keyboard shortcuts and a "copy citation" for reports (data source, release and licence line) | Polish |

## 5. Explored and parked

- **Contributory factors:** still not in open data (FU-001).
- **Link speeds** (TomTom / DfT congestion stats): no open link-level data.
- **iRAP / EuroRAP star ratings and risk maps:** published as maps, not open data. B1's risk layer is our own version.
- **Street Manager roadworks** (DfT open data, monthly): you could correlate collisions with roadworks, but location and date matching is weak. Parked unless you want it.
- **OSM attributes** (lit, lanes, cycle lanes, crossings): coverage varies too much for peer groups. Possibly a later display layer.
- **Minor-road link rates:** not possible from open data (section 2).
- **Mapillary street-level images in site review:** possible (CC BY-SA), but Google Street View links (FU-029) cover it for now.

## 6. Decisions for you

- **D1 — Order:** go with section 1's recommended order, or put something else first?
- **D2 — B1 depth:** full Empirical Bayes with safety performance functions (recommended; it's what makes rankings and before/after defensible), or only rates and peer-group averages first (quicker, with regression-to-the-mean caveats)?
- **D3 — B3 needs writeable tables (`app.scheme`, saved selections).** Fine to add now with no user accounts (single user), or wait for PLAN-006's login so edits can be linked to a person?
- **D4 — Nations:** B6's school data and M10 are England-first. OK to start there and add Scotland and Wales where their data allows?
- **D5 — Anything from your own work** you'd add or drop? For example, the reports your authority actually asks for, or the ranking method used for your local safety schemes (links to FU-019).
