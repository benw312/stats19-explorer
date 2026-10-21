# PLAN-004 — API and frontend for highways engineers

- **Status:** APPROVED 2026-10-05: decisions recorded in section 10; Build 1 in progress
- **Branch:** `plan/004-frontend` (stacked on PR #3)
- **Depends on:** PLAN-003 `mart` layer (merged with PR #3)
- **Users:** highways and road-safety engineers. Their jobs are to spot trends, find the worst collisions and sites, and produce evidence packs for local authorities.

## 1. What the reference tools do (research summary)

| Capability | CrashMap Pro | KeyACCIDENT | Ours |
|---|---|---|---|
| Map with severity-coloured points | ✓ | ✓ ("balloons", severity colours) | Build 1 |
| Address / place search | ✓ address search | — | Build 1: postcode + place/road name |
| Click a collision → details, vehicles, casualties, single-collision report | ✓ pop-up + PDF per crash | ✓ | Build 1 |
| Filters on year, severity, highway authority, road users | ✓ | ✓ | Build 1 (slicers on recorded fields, from `field_catalog`) |
| Custom query builder (AND/OR sets, value/field/list inputs) | ✓ | ✓ multi-table, saved queries | Build 2 |
| Select by point+radius, rectangle, polygon, circle, lasso, polyline buffer | ✓ | ✓ circle + polygon | Build 1: radius, polygon, rectangle. Build 2: route buffer |
| Results table, column chooser, select → zoom, export selected to CSV | ✓ | ✓ Excel multi-sheet | Build 1 |
| Area report (map, summary, list, comments box) → print / PDF, CSV | ✓ | ✓ many templates | Build 1: one well-designed template |
| Time slider / animation | ✓ | — | Build 2 |
| Cluster site analysis (diameter, cap, min count, severity weighting, urban/rural thresholds, ranked and saved sites) | "identify clusters" | ✓ core feature | Build 1 (area page) |
| Heat map | — | ✓ | Build 1 (client-side) |
| Stick diagrams (one row per collision: date, time, severity, light, surface, manoeuvres…) | — | ✓ | Build 1, in reports and site review. Purely recorded fields, the engineer's pattern-spotting tool |
| Cross-tabs, KSI summary, casualty age groups, vulnerable road users, weather | partial | ✓ templates | Build 1: standard report sections |
| Comparison with area norms ("norm percentages") | — | ✓ | Build 1: site vs area over-representation |
| Site monitoring / before-and-after for schemes | — | ✓ | Build 3 |
| Contributory factor analysis | — | ✓ (licensed data) | ✗ not available in open data (FU-001) |

**Not replicated:**
- Contributory factors (we don't have them).
- KeyACCIDENT's data-entry and validation side (police data management).

## 2. Architecture

```
Browser (React + MapLibre) ──HTTP──► api (FastAPI) ──► PostGIS: core / mart / geo
        ▲                                │
        │ vector basemap (PMTiles)       ├─► vector tiles (ST_AsMVT, filtered)
        └── static files (Caddy) ◄───────┘   reports: headless Chromium renders /print routes → PDF
```

| Layer | Choice | Why |
|---|---|---|
| API | **FastAPI** (Python 3.12), psycopg 3 async pool, Pydantic models | Same language and package as the pipeline; typed request validation; OpenAPI docs for free |
| Collision tiles | `ST_AsMVT` endpoints in the API, same filter model as everything else | Filters must apply to tiles, tables, reports and exports identically. Aggregated hex/grid counts below zoom ~11, individual points above |
| Frontend | **React + TypeScript + Vite**, **MapLibre GL JS**, **Terra Draw** (polygon/rectangle/circle/line), TanStack Query, URL-encoded filter state | Open source and no API keys; MapLibre handles millions of points via tiles; shareable URLs for any view |
| Charts | Observable Plot (SVG) | Small, prints crisply into PDF |
| Basemap | Self-hosted **PMTiles** GB extract (Protomaps / OpenStreetMap), served as a static file | No keys or usage limits on the home lab; street-level detail. See D1 |
| PDF | Headless **Chromium (Playwright)** renders a dedicated `/print/...` page with the same components → PDF | One design for screen and paper; the map snapshot renders exactly as on screen |
| Spreadsheets | CSV (zip: collisions, vehicles, casualties) + XLSX (multi-sheet, decoded) | Matches the CrashMap/KeyACCIDENT exports engineers already use |
| Serving | **Caddy** reverse proxy (static frontend, `/api`, basemap), in the same compose stack | Simple TLS/auth seam later (forward-auth to Authentik etc.). See D2 |

### New reference data (`geo` schema, loaded by the pipeline, refreshed quarterly)
All are open data under the OGL, so there are no keys or licence fees:
- **OS Code-Point Open:** ~1.7 M GB postcodes with BNG points → postcode search.
- **OS Open Names:** places, roads (e.g. "A30", "Exeter Road") → place/road search.
- **ONS Open Geography boundaries:** Local Authority Districts, Counties & Unitary Authorities (≈ highway authorities), Police Force Areas → area page, area filters, report headers.
- **DfT average value of prevention per reported collision by severity** (RAS4001) → optional "value of prevention" weighting and totals in site reports (clearly labelled with its source year).
- **Later:** OS Open Roads (route and link analysis), DfT AADF traffic counts (collision rates per vehicle-km).

## 3. One filter model everywhere

A single `Filter` object (JSON, mirrored in the URL) drives every view:
- the map tiles, results table, summaries, reports and exports;
- the hotspot analysis.

That way what the engineer sees on the map is exactly what lands in the PDF.

```
Filter = {
  date: {from, to} | years: [..],
  severity: [fatal, serious, slight],
  area: {type: polygon|radius|rectangle|route_buffer|authority, geometry | code, radius_m?},
  fields: [{table, field, op: in|not_in|between|is_null, values}],   # any coded/measure field from field_catalog
  involves: [pedal_cycle, motorcycle, goods_heavy, ppt, ...],          # mart flags
  time_of_day: {from, to}, day_of_week: [..]
}
```

The server compiles this to parameterised SQL against `mart.collision` (child-table conditions become `EXISTS` subqueries). Field names are validated against `field_catalog`, so nothing from the client is interpolated into SQL.

## 4. Features by build

### Build 1 — "Explore, select, report" + area hotspots (the MVP)

**Map explorer**
- GB map. Collisions are coloured by severity (fatal / serious / slight; colour-blind-safe palette, see D4) and sized by zoom. Below zoom ~11, aggregated counts are shown instead of points. A heat-map toggle is available.
- Search box: postcode (exact) or place / road name (OS Open Names) → map flies there.
- Slicers built from `field_catalog`: date range, severity, road user involved, light, weather, surface, road type, speed limit, junction detail/control, urban/rural, day of week, time of day. Fields not recorded across the whole chosen period show a hint (e.g. "recorded from 2005").
- Click a collision → side panel with the decoded collision, its vehicles (type, manoeuvre, point of impact, driver age band) and casualties (class, severity, age band), plus a link to the DfT/OS map location. Also a "Single collision report" PDF.
- Legend, scale bar, a "data up to <year> (final), provisional from…" badge, and OGL attribution.

**Select and summarise**
- Draw a polygon or rectangle, or drop a pin / pick a postcode with a radius slider (e.g. 25 m–2 km).
- The summary panel updates live:
  - counts by severity and KSI;
  - year trend;
  - casualties by road-user group and age band;
  - conditions breakdown;
  - time-of-day × day-of-week matrix.
- A results table with sortable, chooseable columns; clicking a row zooms to that collision.

**Exports**
- CSV zip / XLSX of the selection: collisions, vehicles, casualties, all decoded.
- **Area report PDF:**
  - title, the engineer's comments box, the filter description;
  - a map snapshot with the boundary;
  - headline numbers;
  - year trend, severity and KSI table, casualty breakdowns, conditions, time matrix;
  - a stick diagram (one row per collision);
  - an appendix listing the collisions;
  - caveats: damage-only collisions aren't in STATS19, and uninjured pedestrians aren't recorded.

**Area and hotspot page**
- Pick an area (highway authority / LAD / police force, or a drawn boundary), a period (e.g. latest 3 or 5 years) and filters (e.g. "wet + dark", "involves pedal cycle").
- Cluster parameters, with KeyACCIDENT-style defaults to confirm (D5):
  - cluster radius (e.g. 50 m urban / 100 m rural, from `urban_or_rural_area`);
  - maximum site diameter cap;
  - minimum collisions (e.g. ≥ 5, or ≥ 2 KSI);
  - severity weighting: count, KSI-weighted, or value of prevention.
- Method: PostGIS `ST_ClusterDBSCAN` on `geom_bng` (metres) over the filtered set. Clusters wider than the cap are split (k-means on the cluster) so corridors don't chain into one "site".
- Output: a **ranked site list** (score, collisions, F/S/s, KSI, trend, value of prevention) with a map of the sites.
- **Site review:**
  - site map;
  - stick diagram;
  - year trend;
  - **over-representation vs the area** (e.g. "wet: site 58% vs authority 17%"; "dark: 44% vs 26%") with counts, so the engineer can see patterns from recorded data;
  - vehicle and casualty mix.
- **Exports:** a "site pack" PDF (one page per site plus a cover page with the ranked table and area map) and a CSV of sites.

### Build 2 — power users
- Query builder (AND/OR sets across collision/vehicle/casualty fields), saved queries.
- Route analysis: draw or pick a road (OS Open Roads) → buffer selection, collisions per km, a strip/linear chart along the route.
- Time slider animation; comparisons of two periods or two areas side by side.
- Saved sites and areas, and named selections, shared by URL.

### Build 3 — schemes and statistics
- **Site monitoring / before–after:** record a scheme (site, date, description); compare the before and after periods, with regression-to-the-mean caveats and an optional comparison area.
- **Statistical hotspots:** Getis-Ord Gi* on a hex grid; network KDE on OS Open Roads links.
- **Collision rates** using DfT AADF traffic flows (per million vehicle-km) for links.
- **Multi-user:** accounts (via reverse-proxy SSO), audit of exports.

## 5. API surface (Build 1)

> **As built:** every endpoint is a `GET` with the filter as `?f=<json>`, so views, exports and reports are shareable URLs and cacheable. PDFs render synchronously (a few seconds; a 25-site pack about 10 s). The README's API table is the current reference.

| Endpoint | Purpose |
|---|---|
| `GET /api/meta` | Data coverage, last run, field catalogue (drives the slicer UI) |
| `GET /api/search?q=` | Postcodes, places, roads → point/bbox |
| `GET /api/tiles/collisions/{z}/{x}/{y}.mvt?filter=` | Filtered points / aggregates |
| `POST /api/collisions/query` | Filter → paged table rows |
| `GET /api/collisions/{collision_index}` | Decoded collision + vehicles + casualties |
| `POST /api/summary` | Filter → summary statistics (counts, trend, breakdowns, time matrix) |
| `POST /api/export/{csv,xlsx}` | Filter → file |
| `POST /api/reports/{area,collision,sites}` | Filter/params → PDF (rendered by headless Chromium; async job if slow) |
| `GET /api/areas?type=` / `GET /api/areas/{type}/{code}` | Boundaries for the area page |
| `POST /api/hotspots` | Area + filter + cluster parameters → ranked sites (cached by parameter hash) |

## 6. Performance targets (home lab, BOSGAME)

- Map tile p95 < 300 ms. Summary for a typical selection (< 50 k collisions) < 1 s.
- Hotspot run for a county over 5 years (~5–15 k collisions) < 10 s.
- Area report PDF < 30 s.
- Frontend initial JS < 300 kB gzipped (MapLibre is the bulk).
- Indexes to add: `mart` / `core` filters commonly combined with date (e.g. `(collision_year, collision_severity)`), GIST on `geom_bng` (exists), and LA codes (exists).

## 7. Testing

- **API:** pytest with the existing PostGIS fixtures. Filter compiler unit tests, including rejection of unknown fields and SQL injection attempts; endpoint contract tests.
- **Hotspots:** fixtures with known geometries (two tight groups 30 m apart, a 2 km corridor) → expected sites, plus the diameter-cap split.
- **Frontend:** component tests for the filter state ↔ URL; Playwright E2E for search → fly to, click → panel, draw polygon → summary → export, and the hotspot run → site pack.
- **Visual regression:** key screens and the PDF pages at 1440 and 1024 px.
- **Accessibility:** keyboard navigation of panels and colour-blind-safe severity colours (axe checks).

## 8. Phasing for Build 1

| # | Work | Size |
|---|---|---|
| 4.1 | Compose additions (api, web, caddy, basemap); FastAPI skeleton; `geo` loaders (Code-Point Open, Open Names, ONS boundaries, RAS4001); `/meta`, `/search` | M |
| 4.2 | Filter model + compiler; tiles; collision detail; map explorer with slicers, search, popup, legend | L |
| 4.3 | Selection tools; summary panel; results table; CSV/XLSX export | M |
| 4.4 | PDF pipeline (Chromium) + area report + single-collision report + stick diagram component | M |
| 4.5 | Area/hotspot page: clustering, ranking, site review with over-representation, site pack PDF | L |
| 4.6 | Deploy to the BOSGAME (DEPLOY.md update), performance pass, E2E and visual tests | M |

Each step will be its own PR with a short plan note. A separate design pass (visual direction, typography, palette) happens before 4.2. It will be done with you: a technical tool for engineers, aiming for a dense but calm UI, not a dashboard template.

## 9. Risks

- **HIGH — scope.** Build 1 alone is a substantial app. Mitigation: phased PRs; each phase is usable on its own (e.g. 4.2 alone is a useful map).
- **MEDIUM — PDF map snapshots in headless Chromium** (WebGL). Mitigation: Chromium with SwiftShader, or a server-rendered static map fallback (e.g. the snapshot rendered from tiles via `maplibre-native`). Spike this early in 4.4.
- **MEDIUM — basemap size and refresh.** A GB PMTiles extract is ~1–2 GB; refresh quarterly with a script.
- **MEDIUM — cluster method acceptance.** Engineers' authorities often have their own criteria. Mitigation: parameters are exposed and recorded on every report, and the defaults are agreed with you (D5).
- **LOW — misreading the data.** Reports carry standard caveats (damage-only not included, CF/RSF not available, provisional vs final, 2024 recoding).

## 10. Decisions (resolved 2026-10-05)

| # | Decision |
|---|---|
| D1 | **OpenStreetMap** via self-hosted Protomaps PMTiles. Known drawbacks are accepted: patchy rural naming in places; OSM road classes can differ from DfT's (analysis uses STATS19's own road class); not OS cartography (OS Open Zoomstack can be added as a toggle later); ~1–2 GB file to refresh periodically |
| D2 | **Home network only** for Build 1; keep the reverse-proxy auth seam |
| D3 | **React + TypeScript + MapLibre + FastAPI** as proposed |
| D4 | **Fatal deep red, serious orange, slight blue** (colour-blind-safe) |
| D5 | **Defaults accepted:** 5 years, 50 m urban / 100 m rural, ≥ 5 collisions or ≥ 2 KSI, KSI-weighted ranking, all adjustable |
| D6 | **Hotspots stay in Build 1** as phase 4.5 |

### Original options

- **D1 — Basemap:** OpenStreetMap via self-hosted Protomaps PMTiles (recommended: street-level detail, house numbers, free), or OS Open Zoomstack (Ordnance Survey cartography, OGL, less detailed at street level)? Both could be offered as a toggle later.
- **D2 — Access in Build 1:** LAN-only on the home lab (recommended), designed so SSO/reverse-proxy auth can be added before anyone outside your network uses it? Or do you need external access early (e.g. to show LAs)?
- **D3 — Stack:** React + TypeScript + MapLibre + FastAPI as above (recommended)? Or do you have a preference (e.g. Vue/Svelte, or Django)?
- **D4 — Severity colours:** fatal = deep red, serious = orange, slight = blue (colour-blind-safe, recommended)? Or a scheme matching what you're used to (e.g. CrashMap's)?
- **D5 — Hotspot defaults:** do you or your authority use standard cluster criteria (radius, period, minimum count / KSI)? If not, I'll propose: 5 years, 50 m radius urban / 100 m rural, ≥ 5 collisions or ≥ 2 KSI, ranked by KSI-weighted score, all user-adjustable.
- **D6 — Split the plan?** Keep hotspots in PLAN-004 Build 1 (as above), or move them to PLAN-005 so the map / select / report flow ships first? Recommended: keep them in Build 1, but as the last phase (4.5).

## Progress

| Phase | Status | Notes |
|---|---|---|
| 4.1 | DONE 2026-10-05 | `geo` loaders and `refresh-reference` (scheduled every 90 days); FastAPI with `/health`, `/meta`, `/search`, `/areas`; compose `api` service. Real load 2.5 min: 1,748,230 postcodes, 970,427 places, 600 GB boundaries (207 highway authorities, matching the 207 STATS19 codes), 80 RAS4001 rows. Endpoint latency on full data: search ≤ 0.14 s, areas ≤ 0.04 s, meta 0.35 s. Caddy and basemap moved to 4.2 (needed with the frontend). |
| 4.2 | DONE 2026-10-05 | Filter model + compiler (whitelisted, parameterised); MVT tiles: pre-aggregated grid for zoomed-out simple filters, live bins otherwise, points from z11 with adaptive fallback to fine bins above 15k points/tile; `core.collision.geom_3857`; collision detail with authority names. Frontend: "survey sheet" design (Plex Sans/Mono, paper/ink, route-green accent), numbered filter sheet driven by `/api/meta` with "recorded from" hints, URL-synced state, search, map with severity colour+size, heat map, collision record card. Basemap: self-hosted Protomaps GB (3.0 GB) + fonts/sprites; Caddy front door with CSP. Initial JS 83 kB gz (map chunk 284 kB lazy). Found and fixed: MapLibre 6 worker not bundled in production; year selects' accessible names. Follow-ups FU-013, FU-014. |
| 4.3 | DONE 2026-10-05 | Selection: radius (+ slider), polygon, rectangle (Terra Draw), or authority picker; area in the URL. APIs: `/summary` (one materialised selection; capped at 200k → 413), `/collisions` paged list, `/describe`, `/export` zip (COPY-streamed) + xlsx. Summary panel with stat tiles, year × severity columns, day × hour matrix, breakdown bars, table views; severity palette re-stepped to pass the dataviz validator (fatal #a8282d, serious #c96a0c, slight #2f6db5). Found and fixed: decoded-view joins decoded all 9.1 M rows (list 15 s → 0.02 s, CSV 55 s → 0.07 s) by querying with `= ANY(ids)`; sheet area changes didn't open the summary. FU-015 (Excel speed). |
| 4.4 | DONE 2026-10-05 | KeyACCIDENT-style stick diagram (`/api/sticks`; SVG pictograms; re-sortable; pattern chips; key), in a new Stick diagram tab with a widen-panel option. PDF reports via headless Chromium (Playwright) printing `/print/area` and `/print/collision/{id}`: map, summary, landscape stick pages, list, caveats; renders limited to two at a time; A4 with page numbers. Found and fixed: production CSP blocked Playwright's eval-based polling (`bypass_csp` in the renderer session; regression test with a real CSP header); WebGL maps cropped because the screen layout width ≠ the printed width (viewport = A4 content width); Chromium printing CSS grid forced one band per page; print map refit after layout; test server reverse-DNS stall (35 s). FU-016 (pictogram review), FU-017 (long reports). |
| 4.5 | DONE 2026-10-05 | See PLAN-005. Greedy cluster circles instead of DBSCAN (sites can't chain along corridors; deterministic). `/hotspots` (+ CSV), `/compare` (26 recorded-field indicators, exact binomial "notable" flags), `collision_ids` in the filter, site pack / single-site PDF. Cluster sites panel: method form, ranked list with sparklines, numbered circles on the map, site review (what's different, year trend, vehicle and casualty mix, sticks, collisions). Kent over 5 years: 0.37 s cold. Print maps are now snapshotted to PNG at 2× (sharper, and frees WebGL contexts). FU-016 closed; FU-018, FU-019 raised. |
