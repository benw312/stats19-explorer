# PLAN-009 — The app's end state: views and navigation

- **Status:** AGREED 2026-10-07 with one change: a pure **Traffic** view stays (section 6). V1 first, then the corridor view.
- **Context:** the app grew in layers. First collisions (Summary), then count-based clusters (Cluster sites), then traffic, junctions and peer comparison (all in "Traffic"). Each part works, but the top level reflects the order we built things in, not how an engineer works.

## 1. What's wrong with the current shape

| Today | Problem |
|---|---|
| **Summary**: charts, collision list, stick diagrams for the filter | Fine, but it knows nothing about traffic. There are no rates, and no "is this area unusual?" |
| **Cluster sites**: count-based clusters on any road | One of two ways to find sites, in its own tab |
| **Traffic**: flows, busiest count points, LA traffic trend, *and* "Worse than similar sites" | Mixes **exposure data** (context) with **network screening** (where to act). The second way of finding sites is hidden here |
| **Cards**: collision, junction and count point, each with its own layout | A junction, a road link and a cluster are all "a site" to an engineer, but they look and behave differently |
| **Map layers**: heat map, traffic, junctions, risk | Fine as toggles, but nothing switches on with the view that needs it |

**Traffic isn't a destination.** Nobody opens the app to look at flows; they open it to understand collisions, and flow is what turns counts into rates and comparisons. So traffic should appear *inside* the views that need it, not as a peer of them.

## 2. How engineers use a tool like this

These are the usual UK local safety scheme workflows, with HSM-style network screening:

1. **Understand an area.** What's happening, where, to whom, and is it getting worse? How does it compare?
2. **Find where to act (network screening).** A ranked list of candidate sites.
3. **Investigate a site.** Collisions, patterns, stick diagram, traffic, how it compares with similar sites, and what a scheme would return.
4. **Look along a route.** Corridor treatments and route studies (B2).
5. **Justify and monitor schemes.** FYRR before; EB before/after once built (B3).

## 3. Proposed end state

Five top-level views, each one workflow, plus a single **site page** that every kind of site opens into.

```
┌ Area ──────┬ Sites ─────────┬ Routes ───────┬ Traffic ───────┬ Schemes (later) ┐
│ what       │ where to act   │ along a road  │ flows only,    │ did it work?    │
│ happened   │                │               │ for design     │                 │
└────────────┴────────────────┴───────────────┴────────────────┴─────────────────┘
              ↓ any row / map click
        ┌ Site page: junction | road link | cluster | collision ┐
```

### 3.1 Area (was Summary)
For the current filter (area + period + conditions):
- **Overview:** today's charts (trend, severity, road users, time matrix, conditions).
- **Collisions:** today's list.
- **Stick diagrams:** today's.
- **Rates and traffic (new home for most of the Traffic tab):**
  - vehicle-km and its trend (LA traffic);
  - collisions per 100M vehicle-km and per head of population, major and minor roads split;
  - **B4 benchmarking** against similar authorities (calibrated by region, as the SPFs now are);
  - the busiest count points move here, as context.

### 3.2 Sites (merges Cluster sites and "Worse than similar sites")
One place for network screening, with the method as a switch at the top:

| Method | Finds | Covers | Strength |
|---|---|---|---|
| **Worse than expected** (default where there is traffic) | Junctions and road links with the largest EB excess | Major roads and junctions with counted arms | Allows for traffic and chance; ranks by what is recoverable |
| **Clusters** | Places with many collisions within a radius | Every road, including minor | Catches sites with no traffic data; matches how most authorities' lists are made |

- **Shared list behaviour:** rank, name, the headline figure, £ a year, and a badge when a site appears in both methods (e.g. a cluster centred on a junction that's in the worst 5%). These are the strongest candidates.
- **The map follows the method:** the risk layer for "worse than expected", cluster circles for "clusters".
- **Pack PDF:** for either list (today's cluster pack, extended).

### 3.3 Routes (new: B2, the corridor view, next after this plan)
- Pick a road (e.g. "A30 from Honiton to Exeter") by search or by clicking two points on it.
- A **strip chart** along the route: junctions and links in order, showing collisions, KSI, flow, rate and excess per segment, with the worst segments marked.
- It also ranks routes: which A roads in the area are worst per vehicle-km.

### 3.4 Traffic (flows only: design information)
Agreed change: a feasibility study needs flows on their own, without collisions. This view is traffic data and nothing else.
- **Area:** the authority's vehicle-km trend (major/minor) and the busiest count points.
- **Count point:** AADF history, vehicle mix (HGV %, buses, cycles, motorcycles), counted or estimated, the road it covers and its length.
- **Junction:** arms and their flows (vehicles entering, major/minor split).
- **Map:** the traffic layer (and junctions); collisions hidden.
- The same count point or junction opened from Area, Sites or Routes shows the full site page, with collisions.

### 3.5 Schemes (later: B3, plus M3 shared site lists)
- Saved schemes: site, measure, date, cost.
- **EB before/after:** did it work, net of regression to the mean and trend?
- FYRR inputs saved with the scheme and printed on the site PDF.
- This is the first view that stores user data, so it waits for remote access decisions (PLAN-006).

### 3.6 Site page (unifies today's cards)
The same skeleton for a junction, a road link (count point) and a cluster; the collision card stays as it is for single records.

1. **Header:** name, type, links to the other site types it overlaps (cluster ↔ junction ↔ road).
2. **Headline figures:** collisions and KSI in the period, the rate, excess and its band.
3. **Collisions by year,** with severity.
4. **What's different** compared with the area (today's cluster analysis, now for junctions and roads too).
5. **Stick diagram.**
6. **Traffic:** arms and flows (junction) or the flow history and vehicle mix (road).
7. **Compared with similar sites:** SPF, EB, value and the FYRR calculator.
8. **Actions:** site PDF, Street View and aerial links, and later "save as scheme".

**Desktop layout:** a wide panel with sections and a sticky section index.
**Phone layout:** the same sections stacked.

### 3.7 Map layers
- Collisions are always available. Heat map, traffic, junctions and risk stay as toggles.
- **Views switch on what they need:** Sites → risk or clusters; Routes → the route highlighted and the risk layer.
- Layer state goes in the URL with the view, so a shared link shows the same map.

### 3.8 URL
- `view=area|sites|routes|traffic|schemes`
- `site=jn:<id>|cp:<id>|cl:<rank>|col:<index>`

The existing `jn`, `cp`, `site`, `view=traffic` and `view=hotspots` links are redirected, so old links keep working.

## 4. What moves where

| Today | End state |
|---|---|
| Summary panel | Area → Overview / Collisions / Stick diagrams |
| Cluster sites panel | Sites → Clusters |
| Traffic → "Worse than similar sites" | Sites → Worse than expected |
| Traffic → LA traffic trend, busiest count points | Traffic (and as context in Area → Rates and traffic) |
| Traffic → authority picker note | Not needed once Area shows rates |
| Count point card | Site page (road link) |
| Junction card | Site page (junction) |
| Cluster site review | Site page (cluster) |
| Header buttons: Summary, Cluster sites, Traffic | Area, Sites, Routes, Traffic (Schemes when built) |

## 5. Steps

| Step | What | Size | When |
|---|---|---|---|
| **V1** | **Navigation:** the Area / Sites / Routes / Traffic header. Traffic becomes flows only; merge the two site lists into Sites with the method switch; redirect old URLs; views switch layers on. | ~1 day | **Before the corridor view**, so Routes has its place |
| V2 | **Corridor view (B2)** inside Routes (§8) | 3–4 days | Done |
| V3 | **Unified site page:** one skeleton, with "what's different" and stick diagrams for junctions and roads (§9) | 2 days | Done |
| V4 | Area → Rates and **B4 benchmarking** (§10) | 2–3 days | Done |
| V5 | **Schemes** (B3 before/after, saved FYRR) | ~1 week | After PLAN-006 decisions |

## 6. Decisions (2026-10-07)

- **Views:** agreed, **plus a pure Traffic view** with no collisions, for design and feasibility work (3.4).
- **Sites:** one list with a toggle between the two methods.
- **Names:** Area, Sites, Routes, Traffic, Schemes.
- **Order:** V1 navigation first, then the corridor view.

## 8. V2: the corridor view (Routes)

**Status:** DONE (2026-10-07), with a road-number box added to the list and the limits in FU-040.

**What a route is.** A road number (A30, M5, A38(M)) within the filter's area. Its pieces are the count point links already scored by the safety model (PLAN-008 T4) and the scored junctions that have an arm on that road. Nothing new is built in the database; it reuses `safety_unit`, `traffic_stretch` and `junction_arm`.

**Ordering.** DfT links don't carry a sequence, so the API chains them. It starts at the most isolated link end (a terminus), repeatedly takes the nearest unvisited link and flips it so its near end comes first. Where the next link is more than a short distance away, it records a gap: the road left the area, or a section isn't counted. The route is then turned to run west to east, or south to north if it runs mostly north–south. A junction is placed on its nearest link of the road (within 150 m), at the fraction of the way between that link's ends.

**API.**
- `GET /api/routes?f=&sort=excess|rate`: roads in the area ranked by net excess collisions (the sum over their links), or by collisions per 100 million vehicle-km for routes of at least 2 km. Each row gives length, collisions, KSI, vehicle-km, rate, excess, the excess valued a year, and the number of links in the worst 5%.
- `GET /api/routes/{road}?f=`: the ordered links (from, to, length, gap before, AADF, collisions, KSI, expected, excess, band, rate, value, geometry), the junctions (link index, fraction, the same figures) and the totals.

**Screen.** Routes has a ranked list. Picking a road gives:
- the totals;
- a **strip chart**: a band strip coloured like the risk layer with junction dots on it, collisions per km as bars whose width is the link length, and AADF below, all on one distance axis, with gaps drawn as breaks;
- the links in order underneath.

Clicking a link or junction opens its site page; closing it returns to the route. The map highlights the route and fits to it, with the risk layer on.

**Counting.** A link's collisions include those at junctions along it (EuroRAP style, FU-037 #4), so a junction's dot overlaps its link's bar. Route totals add links only.

**Limits.**
- Routes that branch (spurs, old and new alignments) chain imperfectly; the gaps show where.
- Minor roads aren't scored, so they aren't routes.
- The period is the safety model's five years, not the filter's.

## 9. V3: the unified site page

**Status:** DONE (2026-10-07). Limits are in FU-041.

**Decisions (2026-10-07):**
- **"What's different" baseline:** compare with the highway authority the site sits in, whatever area is selected. This works with no area set and gives the same answer from every view. Cluster sites switch to it too, on screen and in the site pack.
- **Period:** collision sections follow the filters, as the cards do. "Compared with similar sites" stays on the model's five years, labelled.
- **Width:** site pages open wide on desktop, with a section index; a button narrows them.
- **PDF:** junctions and roads get a site PDF in V3.

**One skeleton** (`components/site/SitePage`) for a junction, a road (count point) and a cluster site. Sections, each with an anchor in the index:
1. **Header:** type, name, place, and **overlaps**:
   - junction: the roads on its arms;
   - road: the junctions on it;
   - cluster: scored junctions and roads within its radius;
   - plus the cluster site containing a junction or road, when clusters are loaded.
2. **Headline figures:**
   - junction: collisions, KSI, rate per million vehicles entering, excess;
   - road: collisions, KSI, rate per 100M veh-km, excess;
   - cluster: collisions, KSI, score, value of prevention.
3. **Collisions by year,** with severity.
4. **What's different** compared with the authority, plus vehicles and casualties by road user. The site's collisions are passed as `collision_ids`, which the junction and road endpoints already return. The base is the same filters over the authority.
5. **Stick diagram,** then the **collision list.**
6. **Traffic:**
   - junction: arms and flows;
   - road: flow, reliability, flow by year and vehicle mix;
   - cluster: the counted roads within its radius.
7. **Compared with similar sites:** SPF/EB, value and FYRR for junctions and roads. Clusters keep the FYRR on their own record, and link to the scored sites inside them.
8. **Actions:** site PDF, zoom, Street View and aerial, and the DfT count point page.

The Traffic view keeps its flows-only cards (§3.4).

**API:**
- `GET /api/areas/at?lon=&lat=`: the highway authority at a point.
- `GET /api/sites/near?lon=&lat=&radius_m=`: scored junctions and counted roads within a radius.
- The count point card gains the junctions on its road.
- `GET /api/reports/junction/{id}.pdf` and `/api/reports/road/{id}.pdf`, rendered from `/print/junction/{id}` and `/print/road/{id}`.

**Sites list:** the "in both" badge. When clusters are computed for the area, a row in "Worse than expected" that falls inside a cluster site shows that site's number.

**URL:** the existing `jn=`, `cp=` and `site=` parameters already make each page shareable, so §3.8's single `site=` parameter isn't needed. Changing it would break saved links.

## 10. V4: Area → Rates and benchmarking (B4)

**Status:** DONE (2026-10-08). Agreed: nearest-neighbour peers, casualties and KSI, filters drive the numerator, PDF page in V4 (§10.6). Limits are in FU-046.

**As built (where it differs from the proposal below):**
- **Revised 2026-10-08 (FU-047):** peers are chosen within the same country, KSI uses DfT's adjusted severity, and years with a possible recording gap are left out of every rate.
- **Peers** use five measures: population (size) was added to the four in §10.3. Without it Kent's nearest included Merthyr Tydfil and Glasgow's Walsall; with it they're Surrey, Hertfordshire and Hampshire, and Edinburgh and Manchester.
- **Region** is DfT's region (from the authority's count points): the nine English regions, Scotland and Wales.
- **Tables** live in `geo` (`authority`, `authority_year`, `authority_peer`), as the other reference builds do, rebuilt as the derived step `authorities` after population, traffic or boundary loads.
- **PDF:** a separate **Rates PDF** (`/api/reports/rates.pdf`, two pages, about 3 s) with no collision cap, because most authorities have far more than the area report's 1,000 collisions. The area report also includes the rates pages when its area is a highway authority.
- **Speed:** about 1 s for a new filter (the casualty join over five years); switching authority under the same filter reuses the cached counts (about 0.02 s).
- **Traffic context** is a table of vehicle-km a year (major, minor, all); the busiest count points stay in Traffic.

**The question it answers:** "Is this authority's record good or bad, once you allow for how much it's travelled and how many people live there, and compared with authorities like it?" These are the figures most authorities put in their annual road safety report.

### 10.1 What's already there, and what's new

| Need | Source | State |
|---|---|---|
| Casualties and collisions per authority | STATS19 `local_authority_highway_current` | Loaded; every collision 2019–25 has it. These are DfT's own authority figures, so they match what authorities publish. |
| All-roads vehicle-km and road length | DfT LA traffic (`geo.traffic_la`, 1993–2025) | Loaded. Cumberland and Westmorland & Furness only from 2023 (Cumbria split). |
| Major-road vehicle-km and length | DfT AADF × link length, by the count point's authority | Loaded (the Traffic view's major trend). **Minor = all roads − major.** |
| Population | ONS mid-year estimates via Nomis (`NM_2002_1`, geography type 423) | **New dataset.** Checked today: all 207 highway authorities, 2021–2025 (Barnsley and Sheffield under their pre-2023 codes, as with traffic). OGL. |

**Major / minor split of casualties:** by the police first road class: motorway, A(M) and A are major (DfT's definition, matching the traffic split). FU-037 showed officers' C/U labels are loose, but major against minor is reliable.

### 10.2 The rates

For the selected authority, over the filter's period (default: the latest five years), each against its **similar authorities**, its **region** and **GB**:

| Rate | Why |
|---|---|
| Casualties per 100M vehicle-km: all roads, major, minor | Exposure-adjusted; the major/minor split separates the strategic network from local streets |
| KSI casualties per 100M vehicle-km | The same, for severity |
| Casualties and KSI per 100k population | What most annual reports lead with |
| Casualties per 100 km of road | Network-length view (rural authorities) |
| Trend: each rate by year | Getting better or worse, against peers |

**Filters apply to the numerator.** Choose pedestrians, or darkness, or motorcyclists, and the rates become "pedestrian casualties per 100k population" and so on, for the authority, its peers and GB alike. Denominators stay fixed. An "Area" filter other than an authority (a radius or polygon) gets the major-road rate only (vehicle-km from the count points inside), with a note that population and benchmarking need an authority.

**Small numbers:** each rate shows its count, and an interval (Poisson 95%) when the count is under 100. Peers are ranked only on five-year totals, never single years.

### 10.3 Similar authorities

ONS's area classification covers districts, not the 21 shire counties that are highway authorities, and CIPFA's nearest-neighbour list isn't open. So: **nearest neighbours from open measures**, the way CIPFA does it:
- **Measures (five-year):** population density, vehicle-km per head, the share of vehicle-km on major roads, and road length per head. Each is log-scaled and standardised.
- **The 15 nearest** authorities by distance on those, within GB.
- **Region** is shown, not used to pick peers: Scotland, Wales and London record collisions at different rates (the SPF finding), so the region's own figure sits beside the peers.
- Each authority's peer list is shown, so it can be challenged.

### 10.4 Screens

**Area → a fourth tab, "Rates":**
1. **Headline tiles:** each rate for the authority, with its peer median, the GB figure and "8th of 16 similar authorities".
2. **Trend:** the chosen rate by year, with the authority, its peers' median (and inter-quartile band) and GB.
3. **Similar authorities table:** each peer with its rates, the selected authority highlighted, sortable; click one to switch the area to it.
4. **Traffic context:** vehicle-km by year, major and minor (moved from Traffic, which keeps its copy), and the busiest count points.
5. **Notes:** sources, the major/minor definition, why counts are the police's authority (DfT figures) and may differ by a few from the map's boundary count.

**PDF:** the area report gains a "Rates and benchmarking" page.

### 10.5 Build

- `population` reference dataset (Nomis CSV; refreshed with the others), table `geo.population (code, year, population)`.
- `mart.authority_year`: per authority and year, population, vehicle-km (all, major, minor) and road length (all, major). Rebuilt after traffic or population reloads. The casualty counts aren't stored: they follow the filter, so they're one grouped query per request over all authorities and years: about 0.06 s with collision filters, 0.8 s when a casualty filter (e.g. pedestrians) needs the casualty table. Responses are cached per filter, as the summary is.
- `mart.authority_peer`: each authority's 15 neighbours and distances, rebuilt with `authority_year`.
- `GET /api/rates?<filter>`: the selected authority's rates by year and in total, its peers, region and GB. Without an authority: GB, plus the major-road rate for a radius or polygon.
- Tests: rate arithmetic, peer selection on a small fixture, the code aliases, the Cumbria years, and the API against fixture data.

### 10.6 Decisions needed

1. **Peers:** nearest neighbours from open measures (§10.3, recommended), or simpler groups by authority type and region (London borough, metropolitan district, English unitary, shire county, Welsh unitary, Scottish council)?
2. **Casualties or collisions** as the numerator? *Recommendation: casualties and KSI casualties, as DfT and annual reports use. Collisions stay in the Overview tab.*
3. **Filters drive the numerator** (§10.2)? *Recommendation: yes; it makes "pedestrian KSI per 100k against similar authorities" one click.*
4. **PDF page** in V4, or after? *Recommendation: in V4. It's the page an annual report would lift.*

## 11. Programme to the end of the core build (agreed 2026-10-08)

> **Superseded 2026-10-09** by PLAN-010 (the programme plan), which keeps the live table. This one is kept for the record.

| # | Work | Depends on | Status |
|---|---|---|---|
| 1 | **Trust in the data:** FU-049 (mark figures that include DfT's documented data issues; an in-app *About the data* page for every caveat) and FU-046 #5 (warn when a date filter skews rates) | — | Done 2026-10-08 (FU-046 #5 not applicable: the app filters whole years) |
| 2 | **PLAN-006 decisions** (D1 domain, D2 login methods, D3 session length, D4 who's allowed, D5 origin JWT check), then remote access | You decide; set up together | Decided and set up 2026-10-08; code in PR #33; go-live waits for the BOSGAME install |
| 3 | **V5 Schemes:** saved schemes, EB before/after, saved FYRR | 2 (first view that stores user data) | Not started |
| 4 | **FU-048 full critical review** of the codebase and data, in a fresh session | 3 (core features done) | Not started |
| 5 | **Ideas:** FU-043 sun position and FU-044 road gradient together (collision context), then FU-045 sketch tool (could jump the queue if a job needs it) | — | Not started |

Small known limits (FU-020, 034, 036, 037, 038, 040, 041) are picked up as housekeeping between items. FU-006 (provisional data) waits for DfT's late-November release.

## 7. The original questions

1. **Four views (Area / Sites / Routes / Schemes) with traffic folded in.** Agree, or keep a separate Traffic view for people who want flows on their own? *My recommendation: fold it in. The traffic layer and the road site page cover "show me the flow here".*
2. **One Sites list with a method switch, or the two lists side by side?** *Recommendation: a switch, defaulting to "worse than expected", with the "in both" badge.*
3. **Names:** "Area", "Sites", "Routes", "Schemes". Or "Summary" instead of "Area" if that's what your colleagues are used to.
4. **Order:** V1 (about a day) before the corridor view, as above.
