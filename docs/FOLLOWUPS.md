# Follow-ups

Items that couldn't be resolved during a piece of work, or that will matter for later development.

**Conventions**

- **IDs:** `FU-NNN`, sequential, never reused.
- **Status:** `OPEN`, `IN PROGRESS`, `BLOCKED`, `DONE`, or `WONTFIX`.
- **Closing an item:** keep it in this file, set the status, and add a one-line resolution.

| ID | Title | Status | Raised |
|---|---|---|---|
| FU-001 | Collision type (shunt etc.) is not in STATS19 — derive it | WONTFIX (decided 2026-10-05) | 2026-10-05 |
| FU-002 | Data guide field names don't always match CSV headers | DONE | 2026-10-05 |
| FU-003 | Choose home-lab host for DB + pipeline | DONE — BOSGAME E2 | 2026-10-05 |
| FU-004 | Harmonise `*_historic` codes using the conversion sheet | DONE | 2026-10-05 |
| FU-005 | Views/marts must be rebuilt after the core schema swap | DONE | 2026-10-05 |
| FU-006 | Load provisional mid-year data (released each November) | BLOCKED until late Nov 2026 release | 2026-10-05 |
| FU-007 | Set validation thresholds from the first real full load | DONE | 2026-10-05 |
| FU-008 | 3,111 casualties share a casualty_reference (mostly 1991–94) | DONE | 2026-10-05 |
| FU-009 | Unlabelled codes: `*_injury_based = -1`, `casualty_type = 33` | DONE | 2026-10-05 |
| FU-010 | Full load timing and footprint baseline | DONE | 2026-10-05 |
| FU-011 | DfT historical revisions file not loaded | OPEN | 2026-10-05 |
| FU-012 | `mart.code_counts` build takes ~7 min | DONE (2026-10-05) | 2026-10-05 |
| FU-013 | Zoomed-out tiles with complex filters take ~0.8 s | DONE (2026-10-05) | 2026-10-05 |
| FU-014 | Mobile: sheet and record panel can overlap after resizing | DONE (2026-10-05) | 2026-10-05 |
| FU-015 | Excel export is slow for large selections (~38 s for 24k collisions) | DONE (2026-10-05) | 2026-10-05 |
| FU-016 | Stick diagram pictograms: review against engineers' expectations | DONE — approved as is | 2026-10-05 |
| FU-017 | Long area reports (e.g. 846 collisions → 64 pages) | DONE (2026-10-05) | 2026-10-05 |
| FU-018 | Large site packs take ~2 s per site in Docker (Kent top 25: 51 s) | DONE (2026-10-05) | 2026-10-05 |
| FU-019 | Cluster site method: compare with authorities' own criteria | SUSPENDED (2026-10-08) | 2026-10-05 |
| FU-020 | Phone layout is cramped (search ~100 px wide; panels cover the map) | OPEN (low) | 2026-10-05 |
| FU-021 | Site number badges overlap when zoomed out over dense areas | DONE (2026-10-05) | 2026-10-05 |
| FU-022 | Hotspot cache and shared site links don't track data releases | DONE (2026-10-05) | 2026-10-05 |
| FU-023 | PDF endings: key/caveats can leave a near-empty last page | DONE (2026-10-05) | 2026-10-05 |
| FU-024 | Map chunk is 294 kB gz, close to the 300 kB app-page budget | WONTFIX (2026-10-05) | 2026-10-05 |
| FU-025 | Dev tooling: no web formatter config; test-client deprecation warning; TypeScript 7 | DONE (2026-10-05) | 2026-10-05 |
| FU-026 | Nice-to-haves noted during Build 1 | OPEN (ideas) | 2026-10-05 |
| FU-027 | Cluster sites: "All sites" should zoom back out | DONE (2026-10-05) | 2026-10-05 |
| FU-028 | Summary tiles: show fatal / serious / slight (and KSI) as % of collisions | DONE (2026-10-05) | 2026-10-05 |
| FU-029 | "Open in Google Maps" (aerial / Street View) for the current view, a site or a collision | DONE (2026-10-05) | 2026-10-05 |
| FU-030 | Deploy rebuilt only api/web: the pipeline image was stale | DONE (2026-10-07) | 2026-10-07 |
| FU-031 | `stats19` CLI not on PATH in containers; reference refresh needs the pipeline service | DONE (2026-10-07) | 2026-10-07 |
| FU-032 | Barnsley and Sheffield: DfT traffic uses pre-2023 authority codes | DONE (2026-10-07) | 2026-10-07 |
| FU-033 | Traffic plum isn't colour-blind-separable from "slight" blue | DONE (2026-10-07) | 2026-10-07 |
| FU-034 | Traffic links (PLAN-008 T2): known limitations | OPEN (low) — #1, #2 done | 2026-10-07 |
| FU-035 | STATS19's 2024 `junction_detail` codes roundabouts as "not at junction" | DONE (2026-10-07) | 2026-10-07 |
| FU-036 | Junctions (PLAN-008 T3a): known limitations | OPEN (low) | 2026-10-07 |
| FU-037 | Collision → link matching (PLAN-008 T3b): known limitations | OPEN (low) — #2 done | 2026-10-07 |
| FU-038 | Safety screening (PLAN-008 T4): limitations and next steps | OPEN (low) — #5 done | 2026-10-07 |
| FU-039 | Pedestrian and cycle counts as a data set | OPEN (explore) | 2026-10-08 |
| FU-040 | Routes / corridor view (PLAN-009 V2): limitations | OPEN (low) | 2026-10-07 |
| FU-041 | Site pages (PLAN-009 V3): limitations and next steps | OPEN (low) | 2026-10-07 |
| FU-042 | Junction arms missing on major roads: spot check | DONE (2026-10-08) | 2026-10-08 |
| FU-043 | Sun position relative to the direction of travel (low-sun glare) | OPEN (idea) | 2026-10-08 |
| FU-044 | Road gradient at each collision (uphill / downhill) | OPEN (idea) | 2026-10-08 |
| FU-045 | Map sketch and markup tool, with drawing export | OPEN (idea) | 2026-10-08 |
| FU-046 | Area → Rates (PLAN-009 V4): limitations | OPEN (low) | 2026-10-08 |
| FU-047 | Data review of 2026-10-08: findings | DONE (2026-10-08) | 2026-10-08 |
| FU-048 | Full critical review of the codebase and data | OPEN — after V5 | 2026-10-08 |
| FU-049 | DfT's documented data issues: mark affected figures | DONE (2026-10-08) | 2026-10-08 |
| FU-050 | Running on the server: versions, updates, logs and diagnostics | DONE (2026-10-08) | 2026-10-08 |
| FU-051 | A failed derived build isn't retried | DONE (2026-10-09) | 2026-10-09 |
| FU-052 | Quick speed-ups for the BOSGAME | DONE (2026-10-09) | 2026-10-09 |
| FU-053 | Clicking quickly between areas froze the API for minutes | DONE (2026-10-09) | 2026-10-09 |
| FU-054 | Drop requests the browser has abandoned | OPEN (low) | 2026-10-09 |
| FU-055 | Feedback button for the pilot | OPEN — after V5, before the pilot | 2026-10-09 |
| FU-056 | Rotate the main database password | OPEN — before the pilot users join | 2026-10-10 |

---

### FU-001 — Collision type (shunt etc.) is not in STATS19 — derive it
- **Status:** WONTFIX — decided 2026-10-05, not implementing
- **Context:**
  - STATS19 open data has no collision-type field.
  - Contributory factors, now road safety factors (RSFs), are withheld as sensitive. They're published only as GB-level tables; the local-authority table RAS0706 is discontinued.
  - There is no vehicle speed field, only the permanent speed limit.
  - The research and a proxy design ("collision signatures") are in `docs/plans/PLAN-002-collision-signatures.md`.
- **Reasons for not implementing:**
  1. **Users would think there's more data than there is.** Derived "signatures" (shunt, loss of control, impairment surrogate, dazzle, etc.) would sit next to real fields. Users would read them as recorded facts or causes, when they are rule-based guesses.
  2. **They can't be validated.** Without the collision-level RSF data, there's no way to measure how accurate any proxy is.
  3. **They'd be unstable over time.** The 2024 recoding (manoeuvre, junction detail) and the force-by-force switch from contributory factors to road safety factors would make proxy trends partly artefacts.
  4. **The recorded fields already answer the questions.** Light, surface and weather conditions, first point of impact, vehicle manoeuvre, skidding, leaving the carriageway, objects hit, junction detail and road user types can be combined by users in frontend slicers. That keeps every filter traceable to a recorded value.
- **If this is ever revisited:**
  - Request collision-level CF/RSF data from DfT (sensitive data form, roadacc.stats@dft.gov.uk). This would give real factors, rather than proxies.
  - Any derived field should be clearly labelled as derived, and validated against that data first.
- **Carry-over:** FU-004 (harmonised historic codes) still matters for slicers, so that 2024-recoded fields such as manoeuvre and junction detail filter consistently across years.

### FU-002 — Data guide field names don't always match CSV headers
- **Status:** DONE — 2026-10-05 (PLAN-003 phase 1)
- **Resolution:**
  - `FIELD_ALIASES` maps three guide names to their CSV headers: `enhanced_collision_severity`, `did_police_officer_attend_scene_of_collision`, `lsoa_of_collision_location`.
  - The 2025 guide now has **0** unmatched fields for our three tables.
  - A permanent warn check, `guide_field_unmatched`, flags any future drift. It ignores other datasets the guide documents (e.g. `historical_revisions`, see FU-011).

### FU-003 — Choose home-lab host for DB + pipeline
- **Status:** DONE — decided 2026-10-05: **BOSGAME E2**
- **Context:** Candidates were the BOSGAME E2 (x86, 12 GB usable), the Pi 5 (arm64, 16 GB, TimescaleDB), the NAS app pool (Pentium), and the MacBook Pro M1 Max (the dev machine).
- **Decision and reasons:**
  - **The workload is light once running.** ETL runs 2–3 times a year (~40 min on the Mac, an estimated 1.5–2 h on the BOSGAME, overnight and unattended). Map and slicer queries are indexed.
  - **The Mac's GPU wouldn't help.** PostGIS clustering is CPU-only.
  - **The MacBook was rejected as the host:** a laptop isn't always on (it sleeps and travels), and Docker on macOS runs in a VM. It stays the dev machine and is used for heavy one-off analysis against a copy of the database.
  - **The BOSGAME fits:** it's always on and x86, and it already runs the Docker tooling (Dockge, Portainer, Forgejo).
  - **The Pi 5 was rejected:** it's slower for spatial work, and keeping this stack separate from TimescaleDB avoids coupling.
- **Delivered:**
  - Runbook `docs/DEPLOY.md`.
  - `backup` compose service: weekly `pg_dump` of core + etl, 4 kept, `BACKUP_DIR` meant for a NAS mount.
  - `POSTGRES_BIND` (localhost by default, `0.0.0.0` opt-in for LAN access).
- **Still to do (your side):** run the "First install" steps in `docs/DEPLOY.md` on the BOSGAME, and create the NAS NFS export for backups.

### FU-004 — Harmonise `*_historic` codes using the conversion sheet
- **Status:** DONE — 2026-10-05 (PLAN-003): no new logic needed
- **Resolution:**
  - DfT already back-fills the 2024-coded fields for all years. Where both are present, they agree 100% with the conversion of the historic value: `vehicle_manoeuvre` 15,988,509 rows, `junction_detail` 8,955,307 rows.
  - `pedestrian_crossing` and `carriageway_hazards` are fully back-filled too.
  - Decision D1 (2026-10-05): **don't fill DfT's gaps**. Restricted lane 1979–98 is 98% a probable default, and journey purpose code 15 merges "other" and "unknown".
  - `mart.field_catalog` shows each field's recorded years and the harmonisation note. The `*_historic` columns stay for pre-2024 detail.

### FU-005 — Views/marts must be rebuilt after the core schema swap
- **Status:** DONE — 2026-10-05 (PLAN-003)
- **Resolution:**
  - Marts are built in `build_mart` during each run, validated with `core`, and swapped in **in the same transaction** (`build→core`, `build_mart→mart`).
  - Views reference tables by OID, so they move with the schemas.
  - Tested: marts follow a reload, a failed validation leaves the existing marts in place, and no `*_previous` schemas are left over.

### FU-006 — Load provisional mid-year data (released each November)
- **Status:** BLOCKED — revisit early December 2026, once DfT publishes provisional Jan–Jun 2026 data (late November) and the file naming can be confirmed
- **Context:** The 1979–latest files only contain final data. Provisional Jan–Jun data is published separately in late November.
- **Next steps:**
  1. Confirm the file naming when the next release appears.
  2. Load it into `core` with an `is_provisional` flag.
  3. Let the next final release supersede it.

### FU-007 — Set validation thresholds from the first real full load
- **Status:** DONE — 2026-10-05 (PLAN-003)
- **Resolution:**
  - Thresholds were set from runs 1–3: quarantine ≤ 0.1% (observed 0), parse failures ≤ 0.01% (observed 0), row count vs previous ≥ 0.99 (observed 1.0).
  - New-code and labelling checks stay as warnings, so a new DfT code never blocks a release.

### FU-008 — 3,111 casualties share a casualty_reference (mostly 1991–94)
- **Status:** DONE — 2026-10-05 (option 2, refined)
- **Context:**
  - The first full load quarantined 3,111 casualty rows as `conflicting_duplicate_key`.
  - They come in pairs: the same `(collision_index, casualty_reference)` but a different vehicle, age, etc. These are real, distinct casualties whose reference was reused (1991: 615, 1992: 657, 1993: 761, 1994: 564, then a tail to 2000).
- **Resolution:**
  - All casualties are kept.
  - The PK is now `(collision_index, casualty_reference, casualty_seq)`. `casualty_seq` is 1 for every normal row, and numbers the reused pairs deterministically (by `vehicle_reference`, then the full row).
  - A new flag, `is_reference_reused`, marks them, and the check `casualty_reference_reused` (info) reports the count.
  - A deterministic sequence was chosen over an identity `casualty_id` because identity values would be renumbered on every rebuild, which would break stable links (e.g. from the frontend).
- **Verified (run 2):**
  - `core.casualty` = 12,102,133, which equals the raw source rows.
  - 3,111 flagged.
  - Casualty quarantine 0.
  - `number_of_casualties_mismatch` 0.0%.

### FU-009 — Unlabelled codes: `*_injury_based = -1`, `casualty_type = 33`
- **Status:** DONE — 2026-10-05 (PLAN-003 phase 1)
- **Resolution:**
  - Added `src/stats19/sql/lookup_supplement.csv`, merged into `lookup_code` with `source = 'supplement'`. The DfT guide always wins if it later defines the same code.
  - `casualty_type 33` → "Personal powered transporter (e.g. e-scooter) rider or passenger". Evidence: 6,103 casualties (2020–25), all linked to `vehicle_type 33`.
  - `collision_injury_based` / `casualty_injury_based = -1` → "Not applicable (before injury-based reporting)".
  - Each supplement row cites its evidence in `note`.
- **Revisit:** when the 2026 guide is published, check whether DfT now labels code 33. If it does, the guide label replaces ours automatically.

### FU-010 — Full load timing and footprint baseline
- **Status:** DONE
- **Resolution:** Run 1 on 2026-10-05 (MacBook M1 Max, Docker PostGIS).
  - Total time 36 min: download 22 min (4.3 GB at ~3.4 MB/s), COPY + typing 3.5 min, keyed core build 11 min.
  - Database size 11 GB.
  - Rows: 9,116,625 collisions; 16,283,094 vehicles; 12,099,022 casualties.
  - 0.2% of collisions have no location (mostly 1979, 1987, 1999–2001).
- **Note for FU-003:** expect roughly 2–3× longer on the BOSGAME E2.

### FU-011 — DfT historical revisions file not loaded
- **Status:** OPEN
- **Context:** DfT publishes `dft-road-casualty-statistics-historical-revisions-data.csv`, documented in the data guide as the `historical_revisions` table: `accident_index`, `vehicle_reference`, `casualty_reference`, `variable`, `effective_date_of_change`, `police_force`. It records corrections made to past records. Found while building the FU-002 check.
- **Next steps (best guess):**
  1. Low priority. Our full reloads already pick up the corrected values.
  2. If an audit trail is wanted (e.g. "why did 2019 counts change?"), load it into `core.historical_revision` and show it in the frontend alongside affected records.

### FU-012 — `mart.code_counts` build takes ~7 min
- **Status:** DONE (2026-10-05)
- **Resolution:** `code_counts` now uses GROUPING SETS: 70 s → 40 s on the full data, output identical (38,934 rows). The ~7 min seen in run 3 wasn't reproducible from the query alone (~70 s); re-check the timing in the next pipeline log.
- **Context:** Run 3 timings: core build 9 min, `collision_summary` 1 min, `field_catalog` 4 s, `code_counts` ~7 min. The count is a `LATERAL VALUES` unpivot over 16 M vehicles × ~30 code columns. Total run ~21 min on the Mac, which is fine for 2–3 releases a year.
- **Next steps (if the BOSGAME run is too slow):** compute per-column `GROUP BY collision_year, col` in parallel, or with `GROUPING SETS`, instead of the unpivot.

### FU-013 — Zoomed-out tiles with complex filters take ~0.8 s
- **Status:** DONE (2026-10-05)
- **Resolution:** Tiles are cached in the API per data load, filter and tile (128 MB LRU): a national tile with a conditions filter is 449 ms the first time, 4 ms after. The first view of a new filter is unchanged; grid dimensions remain an option if that matters on the BOSGAME.
- **Context:**
  - Tile timings measured 2026-10-05 on the full data, MacBook:
    - Default filters (period/severity) use the pre-aggregated `mart.collision_grid`: national zoom 158 ms (latest 5 years), 642 ms (all 47 years); street level ≤ 60 ms.
    - Filters on conditions, road users or vehicle fields fall back to live aggregation: ~0.8 s at national zoom (z5) and ≤ 150 ms from regional zoom.
  - Target was p95 < 300 ms.
- **Next steps (best guess):**
  1. Response cache in the API keyed by (filter hash, z/x/y), invalidated by `etl.run` id.
  2. Optionally add `light_conditions` / `road_surface_conditions` dimensions to the grid (the commonest slicers).
  3. Re-measure on the BOSGAME.

### FU-014 — Mobile: sheet and record panel can overlap after resizing
- **Status:** DONE (2026-10-05)
- **Resolution:** The filter sheet closes when the window crosses below 900 px.
- **Context:** On narrow screens the filter sheet now starts closed and closes when a collision is opened. If a desktop window is shrunk below 900 px with the sheet open, both overlays can show until one is closed.
- **Next steps:** Listen to the 900 px media query and close the sheet when it starts matching. Cover it with a Playwright test at 390 px in phase 4.6.

### FU-015 — Excel export is slow for large selections
- **Status:** DONE (2026-10-05)
- **Resolution:** ~2.5× faster: xlsxwriter instead of openpyxl, and `cursor_tuple_fraction = 1` (the server-side cursor's fast-start plan read 7× slower). Kent, 16k collisions: ~23 s → 9.4 s in Docker. Dates and times are typed Excel values.
- **Context:**
  - Measured 2026-10-05 on the MacBook: 201 collisions 0.3 s; Devon 5 yrs (6k) 7.5 s; Birmingham 10 yrs (24k) 38 s.
  - The time goes on openpyxl writing cells one by one; the query takes about 1 s. CSV exports of the same selections take 0.07–2 s.
  - Excel is capped at 25k collisions, and the UI disables the button above that.
- **Next steps (best guess):**
  1. Try `xlsxwriter` with `constant_memory`, typically 3–5× faster than openpyxl for writing.
  2. Or generate the Excel file in a background job with a "your download is ready" toast. That needs the job queue planned for PDFs in 4.4.

### FU-016 — Stick diagram pictograms: review against engineers' expectations
- **Status:** DONE (2026-10-05)
- **Resolution:** You reviewed the stick diagrams and reports and approved the pictograms as they are.
- **Context:**
  - KeyACCIDENT's stick-diagram documentation is no longer online, so ours follows the published definition: one column per collision, attribute rows, pictograms (especially manoeuvres), re-sortable.
  - Our own conventions:
    - usual states drawn faint;
    - dark shown as a filled disc, with a lamp post for lit or unlit;
    - impact shown as a heavy edge on the vehicle box;
    - flags: S / O / J / Off;
    - casualties: D / P / Ped plus age.
- **Next steps:**
  1. You review a real area report and list anything that reads differently from what engineers expect, e.g. arrow styles, whether a "short" stick (no casualties) or a vehicle–casualty linkage view is wanted, and row order.
  2. Adjust `components/sticks/glyphs.tsx` and the row definitions.

### FU-017 — Long area reports
- **Status:** DONE (2026-10-05)
- **Resolution:** The area report dialog can leave out the stick diagram and/or the collision list (Exeter district: 64 → 3 pages), with a hint pointing to the site pack for long selections.
- **Context:** Reports allow up to 1,000 collisions. Exeter district over 5 years (846 collisions) produced 64 pages, mostly stick bands (16 per landscape band) and the collision list. Rendering is still fast (3.3 s).
- **Next steps (best guess):** Add report options to the PDF dialog, e.g. "summary only" or "summary + list" without sticks, for district-scale selections. For finding problem locations at that scale, the cluster site pack (phase 4.5) is now the better tool: it keeps full sticks per site.

### FU-018 — Large site packs are slow in Docker
- **Status:** DONE (2026-10-05)
- **Resolution:** All report maps are drawn by one shared hidden map instead of a new map each (creating a map was the cost). Kent top 25: 49.6 s → 9.1 s; Devon top 10: 19 s → 6.2 s. The area baseline for comparisons is cached too.
- **Context:** The site pack renders one map per site, one at a time (each is snapshotted to free its WebGL context), at 2× pixel ratio under software WebGL. Devon top 10: 24 pages in 19 s; Kent top 25: 56 pages in 51 s. Well inside the 240 s render limit, and the dialog warns that large packs take up to a minute.
- **Next steps (best guess):**
  1. Render site maps at 1.5× instead of 2× (about 40% fewer pixels) if the BOSGAME is slower.
  2. Or render two maps at a time (well within Chromium's ~16 WebGL contexts).
  3. Or move to a background job with a "ready" notice, shared with FU-015.

### FU-019 — Cluster site method: compare with authorities' own criteria
- **Status:** SUSPENDED (2026-10-08): no local authority list to compare against for the foreseeable future. Pick up again if one becomes available.
- **Context:** PLAN-005 uses greedy circles (50 m urban / 100 m rural, ≥ 5 collisions or ≥ 2 KSI, KSI-weighted). Authorities often publish their own cluster criteria, e.g. different radii, a 3-year period, KSI-only sites, or a minimum of 4 injury collisions.
- **Next steps:**
  1. You check the Devon or Kent site packs against a known local cluster list, if you have one.
  2. Add saved method presets (e.g. "DfT-style 5 yr / 50 m", "KSI only") if authorities differ.

### FU-020 — Phone layout is cramped
- **Status:** DONE (2026-10-07). At ≤560 px the views have their own header row, so search fills the first row (~300 px at 375 px), and site pages are one column with a row of section links. A bottom-sheet layout was judged not worth it for how often the app is used on a phone.
- **Context:** Build 1 targets desktop and tablet. At 390 px the header now fits (shorter "Sites" label, tighter spacing, fixed in housekeeping), but the search box is only ~100 px wide, and the filter sheet and panels cover the whole map. Related: FU-014.
- **Next steps (best guess):** A phone layout with the search on its own row and panels as a bottom sheet over a visible strip of map. Only worth it if engineers use it on site visits.

### FU-021 — Site number badges overlap when zoomed out
- **Status:** DONE (2026-10-05)
- **Resolution:** Site badges use MapLibre symbol collision: where they overlap, the better-ranked site shows; the selected/hovered site always shows. Printed maps keep every number.
- **Context:** At county zoom, sites a few hundred metres apart (e.g. central Exeter) draw their numbered badges on top of each other. Rank 1 is drawn on top, but numbers can still be hidden until you zoom in. The list and hover highlighting still work.
- **Next steps (best guess):** Use MapLibre symbol collision for badges below a zoom level (show the higher-ranked badge, hide the rest), or group overlapping badges into "3 sites" markers that zoom in on click.

### FU-022 — Hotspot cache and shared site links don't track data releases
- **Status:** DONE (2026-10-05)
- **Resolution:** The hotspot cache is keyed on the latest successful pipeline run. Site links are `site=<rank>@<data load>`, and a notice shows when a link predates the latest release.
- **Context:**
  - `/api/hotspots` results are cached in the API process for 15 minutes. After a new DfT release is loaded, results can be up to 15 minutes old.
  - A shared link with `site=3` refers to a rank. After a new release, or a change of period, rank 3 may be a different site.
- **Next steps (best guess):**
  1. Include the latest `etl.run` id in the cache key (one cheap query per request).
  2. Show "data load N" on the site review, and warn when a shared link's load differs from the current one.

### FU-023 — PDF endings can leave a near-empty last page
- **Status:** DONE (2026-10-05)
- **Resolution:** Site packs end with one page for the key and caveats (key lists in two columns in print): single-site PDF 5 → 4 pages. Small sites still give the sticks their own page.
- **Context:** In site packs and single-site PDFs, the stick key and "About this analysis" sometimes don't quite fit, so the licence line spills onto a page of its own (e.g. single site: 5 pages, where 4 would do). Small sites also leave the sticks page mostly empty.
- **Next steps (best guess):** Put the key and caveats on a fixed final page with tighter type. For sites with ≤ 11 collisions, put the sticks on the first site page when it fits.

### FU-024 — Map chunk size
- **Status:** WONTFIX (2026-10-05)
- **Resolution:** Investigated: the 294 kB gz chunk is MapLibre GL itself (Vite names it after `mapStyle`); the Protomaps styles are 38 kB raw. It is loaded lazily after the shell (initial JS 109 kB gz), so nothing worthwhile to trim.
- **Context:** Initial JS is 107 kB gz. The lazily loaded map chunk (MapLibre + Protomaps basemap styles) is 294 kB gz, just under the 300 kB app-page budget; the Vite chunk warning is raised to 1,300 kB to allow it.
- **Next steps (best guess):** Import only the light Protomaps flavour, and check whether `terra-draw` can load only when a draw tool is first used.

### FU-025 — Dev tooling hygiene
- **Status:** DONE (2026-10-05)
- **Resolution:** Prettier config matching the house style (`npm run format`, `format:check`), applied once in its own commit; `httpx2` removes the test-client warning; TypeScript 7 (checked that `tsc -b` still fails on type errors).
- **Context:**
  - **Formatter:** the web code has no formatter config. The code style (single quotes, no semicolons, 120 columns) is followed by hand, and Prettier's defaults would rewrite every file.
  - **Test warning:** pytest shows Starlette's warning that `TestClient` with `httpx` is deprecated in favour of `httpx2`.
  - **TypeScript:** version 7 is out; the project is on 6.0.
  - **Audits** (done in housekeeping): `npm audit` and `pip-audit` found no known vulnerabilities.
- **Next steps (best guess):**
  1. Add a Prettier config that matches the current style and run it once as its own commit.
  2. Switch the test client when FastAPI does.
  3. Try TypeScript 7 on a branch.

### FU-026 — Nice-to-haves noted during Build 1
- **Status:** OPEN (ideas; pick any up as their own items)
- **Ideas:**
  - **Site review:**
    - a "find similar sites" link: other sites where the same indicators are notable;
    - a before/after view once a scheme date is entered. **Now PLAN-009 V5 (Schemes, B3).**
  - **Saved selections:** named areas and saved site lists. **Now PLAN-009 V5 / M3, waiting on PLAN-006 (remote access, user data).**
  - ~~**Exports:** a GeoJSON export of cluster sites~~ DONE 2026-10-07: `GET /api/hotspots.geojson` (true-radius circles drawn in BNG, with the CSV's attributes), plus a "GeoJSON" button beside "Sites CSV".
  - **Area report:** a cluster-sites summary section when the selection is an authority.
  - **Stick diagram:** an option to show casualties linked to their vehicle (the data has the vehicle reference).

### FU-027 — Cluster sites: "All sites" should zoom back out
- **Status:** DONE (2026-10-05)
- **Resolution:** "All sites" flies back to the map view from before the site was opened, or fits all sites when the page was opened from a site link.
- **Context:** Opening a site zooms the map to it, which works well. "← All sites" returns the panel to the ranked list, but the map stays zoomed on that one site.
- **Next steps (best guess):**
  1. When a site is opened, remember the map view (centre and zoom). On "All sites", fly back to it.
  2. If there's no saved view (e.g. the page was opened from a shared `site=N` link), fit the map to all the sites' circles. Fall back to the authority or drawn area.
  3. Small change in `App.tsx` (`openSite(null)`) plus a `getView`/`restoreView` handle from `MapView`. Clicking a collision and pressing "Back to site N" should keep the site view, as it does now.

### FU-028 — Summary tiles: severity shares
- **Status:** DONE (2026-10-05)
- **Resolution:** Fatal, serious, slight and KSI tiles show their share of collisions in the top right (summary panel, area report, site pack), with "<1%" rather than "0%".
- **Context:** The summary panel's tiles show counts for fatal, serious, slight and KSI collisions, but not their share of all collisions, so you have to work it out.
- **Next steps (best guess):**
  1. Add a small muted percentage in the top-right corner of the Fatal, Serious, Slight and KSI collision tiles, e.g. "Serious 20 · 25%". It's a share of collisions; casualties stay a plain count.
  2. Use the same treatment on the site review tiles and the PDF tiles (area report and site pack), so screen and paper match.
  3. Round to whole percentages, with "< 1%" for small non-zero shares, so the parts don't look like they don't add up.

### FU-029 — "Open in Google Maps" for aerial and Street View
- **Status:** DONE (2026-10-05)
- **Resolution:** Google Maps aerial and Street View links (no API key) on the collision record and the site review, plus "map centre" buttons in the map legend. Hidden in PDFs.
- **Context:** The OSM basemap stays as it is. For inspecting a location, a link out to Google Maps gives aerial imagery and Street View without adding imagery to the project (no licensing or API keys).
- **Approach (checked):** Google's documented "Maps URLs" work without an API key and open in a new tab, or in the Google Maps app on a phone:
  - **Aerial:** `https://www.google.com/maps/@?api=1&map_action=map&center=<lat>,<lon>&zoom=<z>&basemap=satellite`
  - **Street View:** `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=<lat>,<lon>`, which opens the nearest panorama.
- **Where the buttons go:**
  1. Map controls: "Google Maps" for the current view (map centre). Google's zoom is about MapLibre's zoom + 1, because MapLibre uses 512 px tiles.
  2. Site review: "Aerial" and "Street View" at the site centre, next to "Zoom to site".
  3. Collision record: the same two links at the collision's location. The record already shows the coordinates.
- **Notes:**
  - These are plain links (`target="_blank" rel="noopener noreferrer"`), so the CSP doesn't need changing and nothing is fetched from Google by the app itself.
  - Opening one sends only the coordinates to Google, and only when clicked. Keep them out of PDFs, or show them as a printed URL if wanted.
  - Bing Maps (`https://www.bing.com/maps?cp=<lat>~<lon>&lvl=<z>&style=a`) could be offered as a second option if useful.

### FU-030 — Deploy rebuilt only api/web: the pipeline image was stale
- **Status:** DONE (2026-10-07)
- **Resolution:** My instructions after PR #14 ran `docker compose build api web`, which left `pipeline` on an image from before the reference-data work (it had no `refresh-reference`, so its 90-day reference refresh had never run on the Mac). Rebuilt it on 2026-10-07. The README now points to DEPLOY.md's `docker compose up -d --build`, which rebuilds every service.
- **Context:** `api` and `pipeline` build from the same Dockerfile but are separate images, so a partial build leaves one behind.

### FU-031 — `stats19` CLI not on PATH in containers; reference refresh needs the pipeline service
- **Status:** DONE (2026-10-07)
- **Resolution:**
  - The Dockerfile now puts `/app/.venv/bin` on `PATH`, so `docker compose exec <service> stats19 …` works.
  - The README gives `docker compose run --rm pipeline refresh-reference --dataset traffic`, as DEPLOY.md already did: `run` uses the image's entrypoint.
  - Downloads need the `pipeline` service, because only it has the `/data` volume. In `api`, the download fails with "Permission denied: 'data'".

### FU-032 — Barnsley and Sheffield: DfT traffic uses pre-2023 authority codes
- **Status:** DONE (2026-10-07)
- **Resolution:** `api/traffic.py` maps E08000038 → E08000016 (Barnsley) and E08000039 → E08000019 (Sheffield) when looking up DfT's authority traffic. All 207 highway authorities now match.
- **If DfT recodes:** drop the aliases. If more authorities are recoded, add them to `LA_CODE_ALIASES`.

### FU-033 — Traffic plum isn't colour-blind-separable from "slight" blue
- **Status:** DONE (2026-10-07). Mitigated: the Traffic view (PLAN-009 V1) hides collisions, so plum and slight blue no longer meet there. In Area, Sites and Routes, traffic is still drawn as rings and dashed lines over collisions dimmed to 30%. Reopen if anyone mixes them up in use.
- **Context:**
  - The dataviz validator shows no fourth hue clears colour-blind separation against the three severity colours (red, orange, blue). Plum `#8a2c99` vs slight blue `#2f6db5` is ΔE 5.2 (deuteranopia), below the 6 floor.
  - Mitigation in T1: traffic is drawn as rings and dashed lines, never filled dots, and collisions fade to 30% while the layer is on. Shape, not colour, tells them apart.
- **Options if it's a problem in use:** make collisions monochrome (severity by size only) while traffic is on; or draw traffic in ink with plum only for the selection.

### FU-034 — Traffic links (PLAN-008 T2): known limitations
- **Status:** OPEN (low)
- **Items:**
  1. ~~**1.8% of current major links unmatched**~~ DONE 2026-10-08: a rescue pass (`traffic_links.with_rescues`). Of the 320, 251 had lost every piece to a neighbour's nearer DfT line, and 69 had no OS link with their number at all (renumbered roads: DfT's A5191 is OS's A458, A28 is A2042). A count point left without a link now takes its own road's piece within 50 m of it, or else the A road or motorway it sits on (within 10 m, running within 20° of DfT's line, whatever OS numbers it). A rescue never leaves another count point without a link. 116 rescued; **204 still unmatched** (1.2%), mostly count points more than 50 m from any piece of their road.
  2. ~~**Same-named forks**~~ DONE 2026-10-08: where a minor road forks and both branches keep its number or name, the stretch follows one: the count point's own OS class first (Nurstead Lane's spur is OS "Unknown"), then the branch most in line. Two branches of that class both within 30° of straight on are carriageways splitting, and both are followed. 3,360 minor stretches got shorter (101k → 93k links); Nurstead Lane went from 5 links to 3.
     - Side effect: 511 junctions whose major arm was counted only from the far side of a fork now have that arm uncounted, so they drop out of the safety model (FU-038). Traffic splits at a fork, so the old count didn't hold there.
  3. **Short DfT links (< 0.5 km) are least reliable:** 62% within ±20% of DfT's length (DfT's 0.1 km rounding accounts for much of it). They matter for T3 only if collisions cluster on them.
  4. ~~**Double rebuild on a full refresh**~~ DONE 2026-10-07: loaders request rebuilds through `reference/derived.py`. Inside `refresh_reference` the requests are collected and each derived table (links, junctions, collision matches, safety) builds once, in dependency order. Before, a full refresh fitted the safety model three times. Loaders run on their own still rebuild straight away.
- **Context:** PLAN-008 §7.


### FU-035 — STATS19's 2024 `junction_detail` codes roundabouts as "not at junction"
- **Status:** DONE (2026-10-07)
- **Resolution:**
  - The record panel shows the junction type from whichever field still has it (`lib/junctionDetail.ts`): the historic field for roundabout, mini-roundabout or slip road, else road type = roundabout.
  - The "Junction detail" filter and the area report's chart carry a note pointing to Road type → Roundabout.
  - The filter itself still can't OR across two fields; a derived junction-type field would be the next step if that's wanted.
- **Finding (2026-10-07):**
  - The 2024 coding of `junction_detail` (13–19) has no roundabout, mini-roundabout or slip road values.
  - Those collisions are 0 ("not at junction or within 20 m") in the new field, in the back-filled years too: 2015–19 has 54k roundabout collisions under historic code 1, all 0 in the new field.
  - From 2024 only `road_type = 1` (about 6k a year) and `junction_control` still identify them.
- **Effects in the app today:**
  1. The record panel shows "Junction: Not at junction or within 20 metres" for roundabout collisions.
  2. The "Junction detail" filter has no roundabout option, and "not at junction" includes roundabouts.
  3. Area report tables split by junction detail inherit the same issue.
- **Fix:** a derived junction type (roundabout, mini-roundabout or slip road from the historic field, or from road type when that's -1), used by the panel, filter and reports. The junction work already uses this rule (`JUNCTION_COLLISION` in `reference/junction_build.py`).

### FU-036 — Junctions (PLAN-008 T3a): known limitations
- **Status:** OPEN (low)
- **Items:**
  1. ~~**Mini-roundabouts**~~ DONE 2026-10-07: from OSM `highway=mini_roundabout`; 85% of police-recorded mini-roundabout collisions now match one (was 6%).
  2. **Signals:** 77% of junctions where police recorded signals are found. The rest have no OSM signal within 30 m, or signals on one approach only. OSM coverage improves over time; re-run `--dataset traffic_signals`.
  3. **Arm count points:** each arm takes the count of the piece nearest the junction. Where an arm's two carriageways have separate one-way counts, only the more common one is used.
  4. **Grade-separated motorway junctions** take the OS junction number only when a slip-road arm is within 750 m. Large interchanges with link roads between their roundabouts may number only some of them.
  5. **Rebuilds:** junctions rebuild after `road_network` and `traffic` (about 2.5 min each), and collisions re-match after every STATS19 load (about 15 s).
  6. **No server tile cache** for junction tiles: they're light from z13, and their counts follow the filter.
  7. **Interchange roundabouts over-count arms** (seen in FU-042's check): each on- and off-slip of a motorway is its own arm, because the two leave the ring more than 60° apart. The M57/M62 roundabout shows 14 arms. COBALT would pair each slip road with its partner (same road number, opposite one-way direction, adjacent on the ring) into one arm. Cosmetic for the page; the safety model uses the flows, not the arm count.

### FU-037 — Collision → link matching (PLAN-008 T3b): known limitations
- **Status:** OPEN (low)
- **Items:**
  1. **Weights are ours:** DfT doesn't publish its weights. 3.9% of our matches score under 75, against DfT's ~1% on OS NGD. A manual review of a sample by score band, as DfT did, would calibrate them.
  2. **C roads:** police "C" and OS "Classified Unnumbered" disagree often (60% score 100+). Police may record C/U loosely; treating C and U as interchangeable for the class score is an option.
     - **DONE 2026-10-08.** 35,548 matches changed (3.2%), all police C/U collisions: 34,349 to a nearer link, 587 to a further one (where the road name or form of way now decides). Matches scoring 100+ rose from 81% to 88%, partly because C/U collisions now get the class points more often. Collision locations, area totals and cluster sites don't change.
     - **Agreed 2026-10-08:** the officer's location is trusted; their C/U label isn't. OS is the source of truth for a road's class.
       - A collision's coordinates never move. The police class only helps choose which nearby OS link a collision is attached to (+15 of the score).
       - Today that +15 can attach a collision to a further road just because its OS class matches the officer's label. That is the "moved by the officer's classification" case, and the alias removes it.
       - Change: `_CLASS` in `reference/collision_links.py` gives police C (5) or U (6) the class points on any OS minor class ("Classified Unnumbered", "Unclassified", "Not Classified", "Unknown"). Among minor roads the choice then rests on distance, name/number and form of way.
       - Checks: report how many matches change and in which direction (expect mostly to a nearer link). Area totals and cluster sites don't change. Tests that compare our match with the police class must treat C/U as one group.
  3. **The rate's length** is our traced OS length (dual carriageways halved). For the 1.8% of major links that are unmatched (FU-034), there's no traced length and no rate.
  4. ~~**Collisions at junctions along a link**~~ By design (EuroRAP style): they count on the link and on the junction. The road page shows both rates, and Routes totals add links only, so no single figure double counts.

### FU-038 — Safety screening (PLAN-008 T4): limitations and next steps
- **Status:** OPEN (low)
- **Items:**
  1. ~~**No map layer yet**~~ DONE: "Worse than similar sites" layer (PLAN-008 §12).
  2. **All-injury models only:** KSI counts are stored. KSI models (sparser, so wider groups) would rank by severity.
     - **Discussed 2026-10-08:** an extra lens, not a replacement. "Wider groups" means broader peer groups of similar sites, not bigger geographic clusters; cluster sites stay as they are. Still weighted by traffic flow. Run it through `safety-check` first and only show it if KSI rankings persist better than chance.
  3. **Urban/rural is a junction-density proxy** (18 within 500 m), validated against the police flag. Edge-of-town sites can fall either side (e.g. Alphington's A30/A377 roundabout is "rural").
  4. **No speed limit:** OS speed data isn't open. If it becomes available, add it to the peer groups.
  5. **Junctions with uncounted minor arms** carry a flag in the model. Typical minor flows by class (from DfT's minor-road sample) would tighten their predictions.
     - **DONE 2026-10-08:** an uncounted minor arm gets the median flow of counted minor arms of its OS class, urban or rural (`safety.typical_minor_flows`): about 7,300 a day for B roads, 1,800 for C and 770 for unclassified. Each class/setting needs 30 counted arms, else the class's median is used. 120,537 of 125,100 scored junctions have an uncounted minor arm; the estimate is typically 7% of their vehicles entering. The model keeps the "minor uncounted" flag as well.
     - Fit: overdispersion (alpha) fell in every junction group, e.g. urban roundabouts 0.62 → 0.53, mini-roundabouts 0.70 → 0.65, rural T-junctions 1.98 → 1.94, and the flow coefficients moved towards 1. `safety-check` persistence is unchanged (junctions 73%, roads 88%).
     - The junction page's safety note gives the estimate: "the model adds a typical flow for their road class (about 11,483 vehicles a day entering)". The arms table and the page's own rate still use counted arms only.
  6. **Minor-road links** aren't scored (single-site counts). Junctions only need their major arms counted.
  7. ~~**The OSM reload** should also rebuild safety~~ DONE: `osm_nodes` now rebuilds safety after re-marking junctions.
  8. ~~**Re-run the out-of-sample check with regions**~~ DONE 2026-10-07: now a command, `stats19 safety-check` (PLAN-008 §13). Ranked within region, 73% of the junctions and 88% of the roads picked from 2016–20 were still in their group's worst 20% in 2021–25. That's the same as ranking nationally (73% / 89%), and well ahead of raw counts (66% / 61%) and raw rates (53% / 29%). National ranking piles 58% of its junction picks into London.
  9. **Regions are four levels.** Police-force levels would go further, but most forces' groups are too small; revisit with a random-effects model if the four-region split proves too coarse.
  10. **FYRR on the PDF:** junction and road site PDFs now exist (V3) and show the excess and its value a year. The FYRR itself needs a cost, so it waits for saved schemes (V5): store the inputs with the scheme and print them.

### FU-039 — Pedestrian and cycle counts as a data set
- **Status:** OPEN (explore)
- **Why:** design and feasibility work needs walking and cycling flows as well as motor traffic, and casualty rates for vulnerable users need an exposure denominator.
- **Sources to evaluate:**
  1. **DfT road traffic counts (already loaded):** every count point has a `pedal_cycles` AADF. Cheapest first step: show it in Traffic and add a cycle casualty rate per cycle-km.
  2. **Local authority automatic counters:** many publish loop and radar counter data (e.g. York, Cambridgeshire, Calderdale), listed on data.gov.uk and DfT's Find Transport Data. Formats differ by council, so each needs its own adapter.
  3. **Cycling Scotland open data:** national monitoring framework counters, near real time, one API for Scotland.
  4. **TfL:** London cycle and pedestrian counts (Active Travel Counts programme) on TfL's open data portal.
  5. **Modelled flows:** Propensity to Cycle Tool (route-network estimates), and DfT's active travel mobile-network data on Find Transport Data. Useful where nothing is counted, but they're estimates.
  6. **Not open:** Strava Metro, Eco-Counter's own portal and city-centre footfall counters vary by licence. Check each before using.
- **Approach:** start with item 1, then a common counter schema (site, mode, direction, hourly or daily counts) with per-source loaders, shown as a separate layer in Traffic.

### FU-040 — Routes / corridor view (PLAN-009 V2): limitations
- **Status:** OPEN (low)
- **Items:**
  1. **Parallel alignments double back:** where two alignments of one road number are both counted (the national A1 between Newark and Peterborough), the ordering zig-zags between them. Area-scale roads order cleanly; national ones can look odd. Splitting a road into connected pieces before ordering, or using OS road-link connectivity rather than geometry, would fix it.
  2. ~~**Net excess hides a bad section**~~ DONE 2026-10-07: Routes can rank by "Worse links" (the excess on worse links only, `sort=worse`). Devon's A30 nets −70 but carries +13 on its worse links.
  3. **Junctions are placed by distance** between a link's two ends, not measured along its line: good enough for the chart, not survey-grade.
  4. **Not on the PDF yet:** a corridor page in the site report would suit route studies.
  5. **Only A roads and motorways:** B roads aren't scored by the safety model (single-site counts).

### FU-041 — Site pages (PLAN-009 V3): limitations and next steps
- **Status:** OPEN (low)
- **Items:**
  1. **Cluster links need clusters computed:** a junction or road page links its cluster site only when the Sites view has run clusters for the area. Elsewhere there's no link, because computing clusters for every page would be slow.
  2. ~~**The "in both" badge works one way**~~ DONE 2026-10-07: cluster rows show "Worse than expected · worst 5%" when a scored junction or road inside them is in its group's worst 20%. It's one query for all sites (`worst_within`), about 0.1 s for 50, and isn't cached, because the safety model rebuilds separately. 11 of Devon's 50 sites have one. A road counts when its link midpoint is in the circle.
  3. **Up to 1,000 collisions per site** feed what's different, the sticks and the list (the filter's id cap). No junction comes close; a long road link over many years could.
  4. ~~**Flow by year in PDFs: labels overlap**~~ DONE 2026-10-07: year axes count their label spacing back from the latest year (`showAxisLabel`), so it's always labelled and never crowds the one before. Area's long-period charts had the same bug.
  5. **No single `site=` URL** (§3.8 dropped): `jn=`, `cp=` and `site=` already make every page shareable.
  6. **"Compared with similar sites" for clusters** is the FYRR on the site's own record, with links to the scored junctions and roads inside. A cluster-level EB estimate would need its own model.

### FU-042 — Junction arms missing on major roads: spot check
- **Status:** DONE (2026-10-08)
- **Resolution:**
  1. **Bristol:** the arm wasn't missing. Marlborough Street was arm 5 (west, uncounted), labelled only "B4051", because arm labels showed the road number before the name. Arms now show both ("B4051 Marlborough Street") on the page and in the PDF.
  2. **Spot check:** 180 junctions sampled across six types (roundabout, signalised, crossroads, multi-arm, T, mini-roundabout; A and B roads) and compared with the roads OSM has meeting each one (`great-britain-latest.osm.pbf`). 23 were flagged; most were noise: roundabout names ("Six Ways Island"), spelling differences, arms OS leaves unnamed, and roads passing 70–450 m away that don't connect.
  3. **One real cause:** links with OS form of way "Shared Use Carriageway" (shared space, no kerbs) were filtered out with private roads, so they never became arms (e.g. Tower Street, Ludlow). They carry traffic, so they're arms now: 3,587 arms, 411 junctions gained an arm and 1,622 new junctions.
  4. **Not found:** no arm lost to node splitting, slip road filtering, arm merging or missing count points. No A or B road link is filtered out as private.
  5. **No build check added:** OS has no reference arm count to compare against. Re-running the OSM comparison after a road network reload is the check; it is a scratch script, not a command (needs the 2 GB extract).
  6. **Over-counting, not missing:** interchange roundabouts give each slip road its own arm (FU-036 #7).
- **Seen:** at a Bristol cluster site, a junction page was missing an arm on quite a major road. Every OS road meeting the junction should be an arm, counted or not, so this is a build gap rather than missing traffic data.
  - **The case:** the roundabout at 51.4593100, −2.5910196 (Bristol city centre). The junction page has no Marlborough Street arm. Start here.
- **Plan:**
  1. Find the Bristol case, then spot-check a sample of junctions (signalised, roundabouts, dual carriageways; urban and rural) against OS Open Roads and aerial imagery until a few failures are found.
  2. Classify why each arm is missing. Candidates to test: the junction is split over several OS nodes (large signalised junctions, roundabouts, dual-carriageway crossings) and only one node's links are counted as arms; slip roads or other forms of way are filtered out; arms of the same road are merged; arms are dropped when they have no count point.
  3. Fix the causes, and add a check to the build that reports junctions whose arm count disagrees with OS.
- **Related:** FU-034 #1 and #2 (count point to OS matching).

### FU-043 — Sun position relative to the direction of travel (low-sun glare)
- **Status:** IN PROGRESS. Planned in [PLAN-012](plans/PLAN-012-collision-context.md). C1 (the sun, headings and the validation) was built 2026-10-11; the app shows it from C3.
- **Idea:** compute where the sun was for each collision from its location, date and time. Compare it with each vehicle's direction of travel to say whether a low sun was ahead (glare through the windscreen), behind (in the mirrors, and in the eyes of oncoming drivers) or to the side.
- **Data we already have:**
  - Location, date and time (local clock time, so BST must be converted to UTC).
  - `vehicle_direction_from` / `vehicle_direction_to`: 8 compass points per vehicle (0 = parked, 9 = unknown).
  - `light_conditions` (daylight / dark) and `weather_conditions` ("fine" is the nearest thing to a clear sky; there's no cloud cover).
- **Method:**
  1. Sun elevation and azimuth from the NOAA solar-position equations (vectorised in Python, or `pvlib` / `astral`). Pure arithmetic, no data to download.
  2. Heading: the 8-point compass is ±22.5°. Where the collision is matched to an OS link (FU-037), take the link's bearing at that point and use the compass only to choose which way along it. That gives a heading to a few degrees.
  3. Store per vehicle: sun elevation, sun bearing relative to heading, and a band (low sun ahead / behind / side / sun up but high / dark). Computed once at load, a few seconds for the full history.
  4. Thresholds to start from (PLAN-002's draft rule): elevation under ~15°, within ±30° of the heading, daylight, not raining or foggy.
- **Use in the app:** a filter ("low sun ahead"), a line on the record panel, and a site indicator ("x% of this site's collisions had a low sun ahead, against y% for similar sites"). The site comparison is the useful one: a junction approach facing east or west that keeps appearing at sunrise or sunset.
- **Caution (FU-001):** we rejected derived "signatures" because users would read them as recorded causes. Sun position is different, a computed physical fact rather than a guess at cause, so present it as a condition ("sun 8° above the horizon, 12° left of the direction of travel"), never as "caused by glare".
- **Limits:** hills and buildings can hide a low sun (FU-044's terrain model could give the hill horizon; buildings, no). The police "dazzling sun" factor isn't in the open data, so it can't be validated collision by collision. Instead, test whether low-sun-ahead collisions are over-represented at sunrise and sunset on east–west roads compared with the same roads at other times.

### FU-044 — Road gradient at each collision (uphill / downhill)
- **Status:** OPEN (idea, raised 2026-10-08). Planned in [PLAN-012](plans/PLAN-012-collision-context.md), C2 (drafted 2026-10-10).
- **Idea:** work out the road's grade and which way it falls at each collision, so each vehicle can be marked as going uphill, downhill or on the level. Compute it once in the pipeline and store it, so the app never loads the terrain model.
- **Open terrain data:**
  - **OS Terrain 50:** all of GB, 50 m grid, OGL. Easy to load, but coarse: it smooths short steep sections and doesn't see cuttings or embankments.
  - **Environment Agency LIDAR Composite DTM (England, 1–2 m, OGL)**, plus Natural Resources Wales lidar and Scotland's partial lidar. Far better for road grades, but national coverage is very large. Only the tiles along roads with collisions would be needed, or fetch on demand from the EA's web service.
  - Suggested route: start with Terrain 50 for every collision, then lidar where it exists, and record which source each grade came from.
- **Method:**
  - Your four-point idea gives the slope of the ground and the direction it falls. Projecting that onto the road's bearing gives the grade along the road.
  - Sampling heights along the matched OS link instead (say ±50 m either side of the collision) is more robust: it follows bends and isn't thrown by the slope across the road. Use this where there's a matched link (FU-037), and the four-point gradient where there isn't.
  - Store the signed grade along the link's direction, then per vehicle uphill / downhill / level from its compass direction.
  - Also store a grade profile per link: Routes could show an elevation profile, and the safety model could use grade in its peer groups.
- **Limits:** a terrain model is bare earth, so a road on a bridge or viaduct gets the valley's slope, and a tunnel the hill's. Flag these from OSM `bridge` / `tunnel` tags and leave their grade blank. Terrain 50 grades are approximate, so show bands (level, 3–5%, 5–8%, over 8%) rather than exact percentages.

### FU-045 — Map sketch and markup tool, with drawing export
- **Status:** OPEN (idea, raised 2026-10-08)
- **Idea:** a sketch mode on the map, usable over any layer (traffic, hotspots, junctions, collisions), so an engineer can mark up a site and export it as a simple drawing.
- **Tools:**
  - Polylines, polygons, circles and rectangles, each with a colour and line style.
  - Text labels and callouts.
  - Click a point for its coordinate, as lat/long and OS grid reference (easting / northing), with copy.
  - Measure length and area, with live labels, using BNG for accuracy.
  - Select, move, edit, delete, and undo.
- **Export:** PNG and PDF at A4 or A3, landscape or portrait. It includes the map view with the active layers, the annotations, a scale bar, a north arrow, a key (the active layers plus each annotation style used), a title, the date, and the required OS / OSM attribution. Optionally fix the scale (e.g. 1:1250 at A3).
- **Build notes:**
  - `terra-draw` (already used for drawing areas) covers lines, polygons, circles, points and selection.
  - Measuring and labels are small additions.
  - The export reuses the site PDF's page frame. The map image needs MapLibre's canvas captured after a full render.
- **Questions for later:**
  - Do sketches need saving and sharing? That belongs with saved schemes (PLAN-009 V5) and user data (PLAN-006). Until then they would be per browser, with GeoJSON export and import.
  - Is a CAD format (DXF) wanted alongside PDF/PNG?

### FU-046 — Area → Rates (PLAN-009 V4): limitations
- **Status:** OPEN (low)
- **Items:**
  1. **Authority counts come from the police's highway authority field**, as DfT publishes them, not the boundary. They can differ by a few from the Summary tab's count, which uses the map boundary. The tab's notes say so.
  2. **Major/minor split follows the police first road class.** FU-037 showed officers' C/U labels are loose, but major against minor is reliable. Using our OS match (`collision_link`) instead would only cover the last 10 years.
  3. **Cumberland and Westmorland & Furness** have no DfT traffic before 2023 (the Cumbria split), so their vehicle-km rates use 2023 onwards. Population and road-length rates use every year. GB and region totals leave out their 2021–22 casualties from vehicle-km rates, so they stay like for like.
  4. **Similar authorities are our nearest neighbours** on five open measures, equally weighted. CIPFA's list uses more measures, but it isn't open. If an authority's own peer list disagrees, a "compare with these authorities" picker would let the user choose.
  5. ~~**Date filters**~~ Not applicable (2026-10-08): the app's filters only offer whole years. Date ranges exist only in the raw API. Day-of-week and time filters just narrow the casualties counted, which is fine for a rate.
  6. **Rates start in 2011:** population on today's boundaries goes back that far. Collisions carry the current authority code from about 2005.
  7. **A drawn area** gets only the major-road rate (count points inside it). Minor-road traffic isn't known below authority level (PLAN-007 §2).

### FU-047 — Data review of 2026-10-08: findings
- **Status:** DONE (2026-10-08): every item fixed or decided, on one branch (PR #31).
- **Done 2026-10-08:**
  - **#1 Peers:** chosen within the same country (England outside London, London, Wales, Scotland). Bath's peers are now Telford & Wrekin, North East Lincolnshire, Redcar & Cleveland and Swindon; Cardiff's are all Welsh.
  - **#2 Recording gaps:** an authority-year below 65% of its share of GB collisions in the three years either side (and expecting at least 30 collisions) is flagged in `authority_year.recording_gap`, rebuilt after each STATS19 load. Flagged years are left out of every pooled rate (the authority's own, its peers', the region's and GB's). They still show, hollow, on the trend, with a note. Nine are flagged today:
    - Stoke-on-Trent 2022, Staffordshire 2022 and B&NES 2023;
    - Gwynedd and Conwy 2024, and Isle of Anglesey 2025, which might be real (20 mph);
    - City of London 2020 (real: COVID);
    - Rutland 2022 and Shetland 2008.

    A list of DfT's documented issues could override the automatic flag later.
  - **#3 KSI:** the Rates tab uses DfT's adjusted severity (fatal plus each casualty's probability of serious), available for every casualty since 2004. The Summary tab and cluster scores still use raw severity (#10).
  - **#5 Trend:** the tooltip says "2025 only" and shows the peers' middle half that year; the subtitle and the peers table name their period.
  - **Bath's rates change:** casualties per 100M vehicle-km 18.0 → 20.4 (2023 left out); KSI per 100M vehicle-km 3.34 → 5.71 (adjusted).
  - **#4 Dual carriageways:** a count's road length halves its "Dual Carriageway" pieces only when both carriageways are traced, judged against the stretch DfT's link leaves for them (`traffic_links.road_length_m`). Road rates, the safety model and corridors use it.
  - **#6 Drawn areas:** major-road vehicle-km for a radius, polygon or authority counts each DfT link for the share of its line inside the area (`traffic.major_vehicle_km`, used by Rates and the Traffic view's trend).
  - **#7:** with a road-user filter, the Summary tab's Casualties tile says "Everyone hurt in these collisions"; the Rates notes say they count only the chosen road users.
  - **#8:** `traffic_aadf.link_length_km` keeps each year's DfT link length, and authority and area traffic use it (today's length when a year has none).
  - **#9 Count point authority codes (0.8% differ from location):** kept as DfT codes them, so our major vehicle-km stays consistent with DfT's own authority totals (minor = all − major). No change.
  - **#10:** cluster-site scores weight each collision by DfT's adjusted probability of KSI (1 + 2p), and value of prevention uses it too. The KSI count stays as recorded. The Summary tab's KSI tile adds the adjusted figure.
  - **#11:** the Rates notes explain that choosing HGVs counts people hurt in HGVs.
- **What was checked:**
  - **National totals match DfT exactly** for 2019–25 (e.g. 2023: 104,258 collisions, 132,977 casualties, 1,624 killed). The raw DfT file matches the database, and nothing was rejected on load.
  - **Traffic matches DfT:** 336.2bn vehicle-miles in 2024, and major roads carry 65% of it.
  - **Rates, Summary and independent SQL agree** for 30 random authorities. The only differences come from counting by the police's authority field rather than the boundary (at most 1.2%, by design).
  - **Site pages:** 40 junction pages, 40 road pages and Bath's top 10 cluster sites match independent queries exactly.
  - **Collisions without a location or road class** are negligible since 2005.
- **Findings (can lead to wrong conclusions):**
  1. **Similar authorities mix countries.** Bath's 15 peers included 4 Scottish and 4 Welsh councils. Scotland records about half England's casualties per vehicle-km (11.7 against 22.9; Wales 14.5; London 83). Peers should come from the same country, with London apart, as the safety model's regions already are.
  2. **Recording gaps look like real changes.** B&NES 2023 has 76 collisions against about 188 in the years either side, in DfT's own file (Avon & Somerset changed recording systems in 2022, per DfT's known issues). A scan of authority-years also flags:
     - Stoke-on-Trent 2021–23 and Staffordshire 2022 (DfT documents Staffordshire under-reporting for 2017–23);
     - Staffordshire 2025 at 1.5×, probably catch-up;
     - several Welsh authorities in 2024–25 at 0.5–0.65 of their usual share (partly the 20 mph change?).
  3. **KSI uses raw police severity.** DfT compares serious injuries across forces with *adjusted* severity, because recording systems differ (CRASH). Adjusting changes a force's KSI by a factor of 0.86 to 1.57, so cross-authority KSI comparisons can be off by up to about 50%.
- **Findings (distort some figures):**
  4. **Dual-carriageway length:** on the 271 major links that are mostly OS "Dual Carriageway", the traced length is a median 0.76 of DfT's, and under 0.7 on 45% of them. Their rate per vehicle-km and safety-model length are inflated by around 30%. Halving is probably wrong where only one carriageway is traced. Corridors use the same length.
  5. **The Rates trend mixes one year with five-year figures without saying so.** The hover shows one year and the peers' spread that year, while the tile and table are five-year figures.
  6. **Drawn areas:** the major-road rate uses the full length of every DfT link whose count point is inside the area, but only the collisions inside it. Small areas come out too low. The link length should be clipped to the area.
  7. **With a road-user filter, Summary and Rates count casualties differently.** Summary counts all casualties in the matching collisions; Rates counts only the chosen road users. Label both.
- **Findings (minor):**
  8. Past years' major traffic uses each link's current length. The AADF file has a length per year, but it isn't kept.
  9. 142 of 17,941 major count points (0.8%) carry a different authority code from where they sit.
  10. **Cluster sites' KSI weighting and value of prevention use raw severity,** so the same issue as #3 applies.
  11. **Casualty share of road users:** "involves HGV" counts HGV occupants only in Rates, so the tab should say so.

### FU-048 — Full critical review of the codebase and data
- **Status:** OPEN. Timing: after the core features are built (after PLAN-009 V5, Schemes) and before the BOSGAME install is relied on for real work.
- **Why:** the 2026-10-08 data review (FU-047) found no miscounts but three method problems that could lead to wrong conclusions. A deliberate, adversarial pass over everything is worth doing once the design stops moving.
- **Scope:**
  1. **Data lineage:** every source, from download to load, derived tables, API and screen. Check what each figure means, its units, period and denominators, and compare national and authority totals with DfT's published figures.
  2. **Calculations:** rates, SPF/EB, clusters, matching scores, value of prevention, FYRR. Recompute samples independently, and test edge cases (small counts, missing years, boundary changes, recoded authorities).
  3. **Consistency:** the same figure shown in different places (tabs, pages, PDFs, CSV/Excel exports, map tiles) must agree, or say why not.
  4. **Weak spots:** silent fallbacks, thresholds without a stated reason, untested paths, performance limits, error handling.
  5. **Documentation:** README, plans, in-app notes and PDF footnotes against what the code actually does; stale or missing explanations.
  6. **Data quality:** recording gaps, source revisions (FU-011), coding changes over time.
- **How:**
  - Run it in a fresh session, so the reviewer isn't checking its own work. Use a written checklist and sampling scripts kept in the repo, so it can be repeated after each data release.
  - **Output:** a report with severity-ranked findings, each with evidence, and FU items for the fixes.
- **Before then:** repeat a lighter version of the FU-047 sampling at each big step.

### FU-049 — DfT's documented data issues: mark affected figures
- **Status:** DONE (2026-10-08). Raised with FU-047.
- **As built:**
  - **The list** is `src/stats19/known_issues.py`: five issues from DfT's page (updated by DfT 29 May 2025, checked 2026-10-08), each with DfT's words, our one-line summary, the forces and years. It's Python rather than YAML, so it's reviewed and tested like code. Review it each September.
  - **API:** `/api/data-issues` returns all issues plus the detected recording gaps; `/api/data-issues/selection?f=` returns the issues touching a filter's collisions, with their years.
  - **Marked figures:** "* DfT documented issue" notes under the Area panel's selection (all tabs) and in the header of every site page (junction, road, cluster). The summary shows on hover or focus, and always on phones. "Read more" opens `/about#<issue>` in a new tab. The Rates trend marks affected years in its tooltip and table.
  - **About the data** (`/about`, linked from the header): DfT's issues in their words with the source; the detected recording gaps table; how figures are counted (severity and adjusted KSI, boundary or police field, rates and similar authorities, matching, safety comparison, traffic); sources and licences.
  - **PDFs** (area, rates, site) print the issues in full. **CSV/Excel** exports add a `dft_data_issue` column per collision, and the About sheet lists the issues.
  - **Not done:** the map's collision layer has no marker; the notes cover the selection instead.
- **Why:** DfT publishes known data issues by force and year, e.g. Avon & Somerset's 2022 system change ("key data was missing") and Staffordshire's under-reporting 2017–2023 ([known issues](https://www.gov.uk/government/publications/reported-road-casualty-statistics-background-quality-report/road-casualty-statistics-known-data-issues)). The app should keep using the published data, but say when a figure includes an affected force and year.
- **Proposal:**
  1. **A curated list in the repo** (`data/known_issues.yml`): force or authority codes, years, kind (under-recording, delay, coding), DfT's wording, the source link, and the date checked. Review it each September, when DfT updates the page with the annual statistics.
  2. **Mark, don't hide.** Any figure whose selection overlaps an issue gets an asterisk: "DfT documented issue". This covers Area tiles and trend years, Rates cards, trend points and peer rows, site pages, cluster sites and exports.
  3. **Hover or tap** gives a one-line summary and "Read more", linking to an in-app **About the data** page (`/about#known-issues`) with each issue in DfT's words and the link to DfT's page. Not the README: engineers using the app never see it. The README links to the same file for developers.
  4. **PDFs** print the footnote text, since hover doesn't print. CSV/Excel exports add a column with the issue reference.
  5. **Two kinds of flag, kept apart:** the documented issue (curated) and the possible recording gap (detected from the data, FU-047 #2). Only measurable gaps are left out of rates; a documented issue alone just marks the figure.
- **The About the data page** is also the home for the other caveats now spread across notes: adjusted KSI, police-field versus boundary counts, same-country peers, and how matching and rates work.

### FU-050 — Running on the server: versions, updates, logs and diagnostics
- **Status:** DONE (2026-10-08). Raised during the BOSGAME install (FU-003).
- **Why:** development is on the Mac and the app runs on the BOSGAME. To debug a problem there, we need to know which code is running, find the log line behind an error, see browser crashes at all, and gather the server's state without exposing secrets. Updates needed a safe routine too.
- **As built:**
  1. **Version stamp:** the images carry the git commit and build time (`GIT_COMMIT`, `BUILD_DATE` build args; `stats19.version`). They show at `/api/health`, at `/api/meta` and on the About page ("This copy of the app").
  2. **Request references:** every API response has `X-Request-Ref`, and every error envelope has `error.ref`. The API logs one line per request with the ref (`stats19.api.request_log`). Unhandled exceptions are logged with their traceback and returned as a 500 envelope. The app adds "(ref …)" to server-error messages.
  3. **Browser errors:** uncaught errors, unhandled rejections and render crashes go to `POST /api/client-errors`, which only writes a log line. It is rate-limited (30 per 5 minutes) and validated, and newlines are flattened so a report can't fake log lines. The browser sends each distinct error once, at most 10 per page. A crash screen with the ref replaces the blank page.
  4. **Log rotation:** json-file, 10 MB × 5 per container.
  5. **`scripts/update.sh`:** refuses on local edits or mid-load; pull, stamped build, migrate, restart, health check; prints how to roll back.
  6. **`scripts/diagnose.sh`:** a paste-able report. Secrets are stripped by `scripts/redact.py`: the `.env` values whose names contain PASSWORD, TOKEN or SECRET, database URL passwords and JWTs.
- **Found on the way:** `stats19 serve` didn't pass the Access settings to the app, so remote requests would all have been refused. Fixed in PR #35.
- **Not done:** no metrics or alerting beyond the existing Uptime Kuma and Dozzle (DEPLOY.md → Monitoring). The "busy" check in `update.sh` reads the pipeline's last log line. It doesn't see a one-off `docker compose run` in another terminal.

### FU-051 — A failed derived build isn't retried
- **Status:** DONE (2026-10-09). Raised on the first BOSGAME load (FU-003), which ran out of shared memory in `build_traffic_links` (fixed in PR #38, `shm_size` on `db`).
- **Problem:** each reference loader committed its dataset and its `geo.reference_refresh` row before the derived builds ran at the end of `deferred()`. If a build then failed, every dataset already counted as fresh. `watch` wouldn't try again for 90 days, so traffic links, junctions, collision matches, safety and authority rates stayed missing or stale. The re-match after a STATS19 load had the same gap: a failure was only logged.
- **As built:**
  1. **`etl.derived_pending`** (migration 006). `rebuild()` records each build it's asked for, and each row is deleted only when that build commits. A full junction build also clears `junction_osm` and the new `junction_collisions` step.
  2. **Retried at the next check:** `refresh_if_stale` runs pending builds even when every dataset is fresh, and a refresh runs them with its own builds. `watch` therefore retries a failure the next day, or straight away after a STATS19 load, since the reference check follows it.
  3. **The STATS19 load's re-match** (junction collisions, collision links, safety, authorities) goes through `rebuild()`, so a failure there is retried too.
  4. **`stats19 rebuild-derived`** runs what's pending now; `--step safety` (repeatable) forces named builds. `stats19 status` lists anything pending.

### FU-052 — Quick speed-ups for the BOSGAME
- **Status:** DONE (2026-10-09). The remaining slow spot goes to FU-048.
- **Why:** the slowest requests on the BOSGAME's first day (from the API's request log): rates 2.2 s, traffic summary 1.4 s, sites near a point 1.3 s, top sites 1.1–1.2 s, meta 0.4–0.6 s.
- **As built** (Mac timings, warm):
  1. **`/api/meta`** counted every collision (about 2.5 million rows) on every page load: 225 ms. It's now cached until the next data load or reference refresh: 2.5 ms.
  2. **`/api/safety/top` with an area** wrapped the area test in a per-row `EXISTS`, so it checked all 125k junctions instead of using the spatial index: 560 ms. The area now filters `geo.safety_unit` directly: 29 ms.
  3. **`/api/sites/near`** (clicking the map) had no BNG spatial index on `geo.junction` or `geo.traffic_stretch`, so it scanned a million junctions: 410 ms. Migration 005 adds the indexes, and the builds recreate them: 3 ms.
  4. **JIT off for the API's connections.** Postgres spent about 300 ms compiling queries whose cost it overestimated. API queries are short, so the compiling never paid off.
  5. **Postgres memory:** `PG_SHARED_BUFFERS=3GB` on the BOSGAME, up from the cautious 1 GB default; `.env.example` says how to size it.
- **Left for FU-048:** the first `/api/rates` call for a filter counts casualties for every authority and year: 0.8 s for five years and 3.3 s for all years on the Mac. Each filter is cached afterwards. A pre-aggregated table of casualties by authority, year and severity would fix it, but filters on other fields would still need the full count.

### FU-053 — Clicking quickly between areas froze the API for minutes
- **Status:** DONE (2026-10-09). Found on the BOSGAME through the tunnel: after 6 or 7 quick authority changes, map tiles took 30 s to 5 minutes and some failed with `PoolTimeout`. The database was idle the whole time.
- **Cause:**
  - FastAPI runs the synchronous `get_conn` dependency in its pool of 40 worker threads, both to take a connection and to give it back.
  - Each area change sends dozens of requests, mostly tiles. These filled every thread with requests waiting for one of the 10 connections.
  - A request that had finished then had no thread to return its connection with, so everything waited out the pool's 30 s timeout.
  - Reproduced on the Mac: 8 large authorities, 1.5 s apart, gave a median tile time of 30 s.
- **As built:**
  1. **Database slots:** `db_slot` is an async dependency that waits on a semaphore the size of the pool, on the event loop. Only a request holding a slot takes a thread and a connection, so threads are always free to return connections. The same burst now gives a slowest tile of 0.5 s. `tests/test_db_slots.py` reproduces the deadlock with 3 threads and 2 connections.
  2. **`work_mem=32MB` for the API's connections.** At 64 MB, ten heavy queries at once (cold all-years rates) overflowed the database's shared memory. 32 MB is as fast for these queries.
  3. **`shm_size: 2g` on `db`,** up from 1 GB (PR #38), for headroom.
  4. **Slow-query log:** Postgres logs queries over 2 s (`log_min_duration_statement`).

### FU-054 — Drop requests the browser has abandoned
- **Status:** OPEN (low). Left over from FU-053.
- **Idea:** when you pan the map or click past an area, the browser cancels requests it no longer needs, but the API still runs them. Checking for a disconnect before taking a database slot would skip them.
- **Why not done:** the request log and the Access check are `@app.middleware("http")` layers, which relay messages between tasks. A disconnect reaches the handler only after a few milliseconds of waiting, and Starlette's `is_disconnected()` never saw it in tests. The fix is to rewrite both as plain ASGI middleware, which deserves its own careful PR because one of them is the Access check. FU-053 already stops the pile-up from freezing the app, so this only saves wasted work.

### FU-055 — Feedback button for the pilot
- **Status:** DONE (2026-10-10). Built as specified below, with these differences:
  - **Triage:** `stats19 feedback` lists items. `--seen ID` and `--done ID` move one along, with an optional `--note`.
  - **`diagnose.sh`:** shows the newest five items rather than only a count.
  - **What the API role may do:** it may only insert and read. Triage is done as the owner, through the CLI.
  - **Feedback stores a second reference:** the API log reference of the request that saved it, as well as any error reference.
  - **Still open, both optional:** a push to your phone, and an in-app list once accounts exist.
- **Original plan:** its own small PR after V5 and before the pilot users join (PLAN-014 C1). Asked for on 2026-10-09.
- **Goal:** a pilot user who hits a problem or has an idea can say so in under a minute, without leaving the page. You get enough context to reproduce it.
- **The control:**
  - A "Feedback" button that is always in the header (not a floating bubble over the map).
  - It opens a small dialog: keyboard accessible, focus kept inside, Esc closes it, and every field labelled.
- **What the user gives:**
  - **Type:** Problem / Idea / Question / Something I liked. One tap, defaulting to Problem.
  - **What happened, or what you'd like:** free text, required, up to 2,000 characters. A hint suggests "what you expected and what you saw".
  - Optionally, **"OK to contact me about this"** (on by default). Access already gives the email.
- **What's captured automatically, and shown in the dialog before sending:**
  - The **full URL**. The view, area, filters and selected site are all in it (PLAN-009 §3.8), so opening it reproduces the screen.
  - The app version (commit), screen and window size, browser and OS.
  - The time, and who (the Access email, or "LAN").
  - The last error reference, if one was shown this session. The crash screen gets a "Tell us what you were doing" link that opens the dialog pre-filled.
- **What isn't captured:** no screenshot at first. Capturing the map canvas is heavy and unreliable (WebGL), and the URL reproduces the screen. Consider an optional "attach a screenshot" upload later, if pilots ask for it.
- **Storage:**
  - A table `app.feedback`: `org_id`, kind, message, url, version, user_agent, viewport, error_ref, `created_by`, `contact_ok`, and status (`new` → `seen` → `done`, plus a note).
  - Stored rather than only logged, so it can be triaged.
  - It uses the V5 write safeguards (same-site JSON, rate limit, the API role's `app`-only rights) and is included in the daily `app` backup.
- **Seeing it:**
  - `stats19 feedback` lists new items (the CLI, on the BOSGAME), and `--done <id>` closes one.
  - `scripts/diagnose.sh` shows the count of new items.
  - Optional later: a push to your phone (ntfy or email) when one arrives, and an in-app list once accounts have roles (PLAN-014 C2).
- **The thank-you:** "Thanks, sent (ref a1b2c3)". The reference matches the API log line, as with errors.
- **Size:** about a day.

### FU-056 — Rotate the main database password
- **Status:** OPEN. Do it before the pilot users join (PLAN-014 C1). About 15 minutes on the BOSGAME.
- **Why:** on 2026-10-09 the `STATS19_DATABASE_URL` line from `.env`, with the owner (`stats19`) password in it, was pasted into a Claude conversation. The database isn't reachable from outside, but the password should be treated as exposed.
- **Steps (on the BOSGAME, in `/opt/stacks/stats19`):**
  1. Take a fresh backup first (DEPLOY.md → Backups).
  2. Make a new password: `openssl rand -hex 24`. Don't paste it anywhere else.
  3. Change it in Postgres. `POSTGRES_PASSWORD` is only read when the volume is first created, so editing `.env` alone does nothing: `docker compose exec db psql -U stats19 -d stats19 -c "\password stats19"` and type the new one twice.
  4. Put the new password in `.env`, in both `POSTGRES_PASSWORD` and `STATS19_DATABASE_URL`.
  5. `docker compose up -d`, then `scripts/diagnose.sh`. The API, the backups and the pipeline should all connect.
  6. Do the same for the API role's password (`STATS19_API_DB_PASSWORD`, if set) only if it was ever shared too.

### FU-057 — Schemes (PLAN-011 S2): known limits
- **Status:** OPEN (low). Raised 2026-10-10 when S2 was built.
- ~~**A junction footprint counts every collision within 25 m.**~~ **DONE in S3 (2026-10-10), agreed like for like:** a junction scheme counts only the collisions STATS19 records at a junction, as the junction page and its model do; a link scheme counts the rest. The by-year chart uses the same rule.
- **A route scheme is the whole corridor within the selected area.** There's no way yet to pick a section, such as "from junction 4 to junction 6". Pick an area first to narrow it. A section picker on the strip chart would fix this.
- **An authority area scheme saves the boundary as drawn on the map** (simplified to 25 m), not the full-detail boundary. That's fine for counting collisions. It could matter only for a collision within a few metres of the border.
- **Footprints can't be redrawn when editing.** To change the site, save a new scheme and delete the old one.
- **No map layer for scheme footprints yet.** That's S4. The page zooms to the footprint instead.
- **The chart is descriptive.** The page says so until S4 shows the evaluation's result card.

### FU-058 — Schemes: effects beyond the footprint (idea)
- **Status:** IDEA. Raised 2026-10-10 by the user while agreeing FU-057.
- **The question:** did a scheme move collisions elsewhere, or help further afield? For example:
  - traffic calming that diverts traffic onto a parallel road;
  - signals that queue traffic back through the junction before;
  - a 20 mph zone whose effect spreads to the roads around it.
- **Why it isn't simple:**
  - **The data is noisy.** A ring around a junction holds many more collisions than the junction itself, so a real shift of a few collisions is easily lost.
  - **Wider areas overlap other changes:** other schemes, new developments, roadworks.
- **A possible shape, to be worked out before building:**
  - A "surrounding area" ring, say 200–500 m beyond the footprint, or the roads a diversion would use, evaluated with method B against the rest of the authority.
  - Shown next to the scheme's own result, with its CI, as "nearby roads".
  - Flows from the traffic counts, where they exist, to tell diverted traffic from changed risk.
  - A power check first: would the ring's counts detect a change of the size expected? If not, say so rather than show a result.
- **Background:** the road safety literature calls these *migration* (collisions move to nearby sites) and *spillover* (benefits spread beyond the treated site). Both are documented for safety cameras and area-wide traffic calming, and both are hard to measure without many schemes.

### FU-059 — Scheme evaluation (PLAN-011 S3): known limits
- **Status:** OPEN (low). Raised 2026-10-10 when S3 was built.
- **The site's flow is the model's 5-year average in every year.** The trend comes from the peer group's calibration factors, which include the group's own traffic growth. A scheme that changes the site's own traffic (diverting it away, say) isn't allowed for. Using each year's AADF would fix this, where the site's counts are yearly rather than estimated.
- **A link scheme's footprint counts about 8% more collisions than its model does.** It counts everything within 25 m of the line that isn't a junction collision. The model counts collisions matched to the link itself, so slip roads and parallel roads within 25 m add a few. The bias in θ is small, because the same footprint counts both periods and EB leans on the site's own count for busy links. Counting through the link matches instead would remove it, but those cover only the last 10 years.
- **The models are fitted on the latest five years,** which can include a scheme's after period. Hauer's method assumes the reference group is untreated. With thousands of sites per group, one scheme barely moves the fit. Many schemes in one group would need a model that excludes them.
- **Other schemes in the comparison area aren't excluded** (PLAN-011 §8). Later: leave recorded schemes' footprints out of the comparison counts.
- **Junction footprints and the junction match differ slightly:** the footprint is the match area, while the match takes each collision's nearest junction. Close junctions can share a few collisions. They agree within 1% over 500 sample junctions.
- **No UI yet.** The result card is S4.

### FU-061 — Sun and headings (PLAN-012 C1): known limits
- **Status:** OPEN (low). Raised 2026-10-11 when C1 was built.
- **2.2 GB on disk** for the two context tables, mostly row overhead on 15 M vehicle rows. Smaller codes for the source and band would save about 15%. A numeric collision key would save more, but core has none.
- **Exact headings only for the last 10 years, and away from junctions.** That's 0.67 M of 15.1 M vehicles. Older years, and every junction collision, use the compass (±22.5°). Matching earlier years to links (FU-037) would widen this.
- **Hills and buildings aren't modelled.** A low sun behind a ridge still counts as "low ahead". C2's terrain could give the hill horizon later (PLAN-012 "Later").
- **"Fine" weather isn't "sunny".** STATS19 records no cloud cover, so the fine-weather bands include overcast days. That dilutes the glare signal rather than biasing it.
- **The build holds a year in memory,** at most 1.1 GB on the Mac. That's fine on the BOSGAME, but watch it alongside the other derived builds.
