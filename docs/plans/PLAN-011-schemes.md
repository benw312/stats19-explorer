# PLAN-011 — V5 Schemes: saved schemes and before/after monitoring

- **Status:** AGREED 2026-10-09. All five decisions in §9 are as recommended. S1 built (see §10).
- **Context:** PLAN-009 §3.5 (V5), PLAN-007 B3 (before/after) and B5 (FYRR, done). This is the core build's last view, and the first that stores user data (PLAN-010 §2).

## 1. Goal

An engineer can:
1. **Record a scheme** at a site: a junction, a road link, a cluster, a stretch of route or a drawn area. A scheme has a measure, dates and a cost, plus the FYRR assumptions used to justify it.
2. **See whether it worked** once after-data arrives: the change in collisions, corrected for regression to the mean and the general trend, with a confidence interval. Also the collisions saved and their value, and the achieved first-year return against the one expected.
3. **Keep a list** of schemes with their status ("monitoring: 14 of 36 months of data"), and print a **monitoring report**.

Topical use: the Wales default 20 mph limit (September 2023), recorded as an area scheme.

## 2. What a scheme stores

The new `app.scheme` table:

| Field | Notes |
|---|---|
| `id` | uuid |
| `org_id` | The organisation the scheme belongs to. Every `app` table has it, defaulting to a single organisation until accounts exist (PLAN-014 D5). It's added now, so live data never has to be migrated when customers arrive |
| `name`, `description` | Free text |
| `measure` | One of a short fixed list (D2) plus "other". The list makes schemes comparable later ("how did our signal schemes do?") |
| `site_type` | `junction` · `link` · `cluster` · `route` · `area` |
| `site_ref` | The site's id when saved (junction id, count point, road name). It's a hint only, see below |
| `geom_bng` | **A snapshot of the site's footprint:** a junction's match area, a link's stretch, a cluster's circle, a route section or a drawn polygon |
| `works_start`, `works_end` | The construction period, which is left out of both periods. `works_end` is "completed" |
| `before_years`, `after_years` | Default 3 and 3 (D3) |
| `cost` | £ |
| `fyrr` | jsonb: the expected reduction, collisions a year and value per collision at the time. Saved from the existing FYRR calculator |
| `created_at`, `updated_at`, `created_by`, `updated_by` | `*_by` is the Access email for remote edits, or "LAN" (D4) |

**Why a geometry snapshot, not just the id:** junction ids, cluster ids and peer groups can change when the pipeline rebuilds them (new OS Open Roads, new data). The scheme's collisions are counted from its own stored footprint, so its result never moves because of a rebuild. The site id is used only to link back to today's site page and to find the site's current safety model. If that site no longer exists, the evaluation falls back to the comparison-group method (§3) and says so.

## 3. How "did it work" is worked out

Two methods, chosen by site type:

**A. Empirical Bayes before/after (junctions and links).** This is the standard method (Hauer, *Observational Before–After Studies in Road Safety*), and the reason B1's safety models exist.
1. Get N_B and N_A: the injury collisions in the footprint in the before and after periods, leaving out the works.
2. Use the site's safety performance function to predict μ_B and μ_A for each period. The flows come from that period's AADF, and the general trend from yearly calibration factors (observed ÷ predicted for the whole peer group, per year).
3. Combine the model with the site's own history. Weight w = 1 / (1 + α·μ_B); EB_B = w·μ_B + (1 − w)·N_B.
4. Work out the after count expected without the scheme: π = EB_B × μ_A / μ_B.
5. Compute the index of effectiveness θ = (N_A / π) / (1 + Var(π)/π²), where Var(π) = π·(μ_A/μ_B)·(1 − w). Then the 95% CI, and the % change = 100·(θ − 1).

**B. Comparison group (areas, routes, clusters, and any site without a model).** Compare the change at the scheme with the change in a comparison area: by default the rest of the authority on the same road classes (D5). This is an odds ratio with a CI. It corrects for the trend but **not** for regression to the mean, and the result says so in words.

**What the result shows:**
- The % change with its CI, in plain words:
  - "Collisions fell by 38% (95% CI 12% to 56%) more than expected."
  - Or "Not enough evidence of a change yet."
- Collisions saved a year and their value (RAS4001), and the achieved FYRR next to the expected one.
- **Severity:** the method counts all injury collisions. KSI is shown descriptively, before against after, with no correction, because KSI counts are usually too small for EB.
- **Data so far:** "14 of 36 months", from the latest loaded year. DfT publishes once a year in September, so the after-data arrives in steps.

## 4. Where it appears in the app

- **"Save as scheme"** on every site page (junction, link, cluster) and on an area or route selection. It opens a short form pre-filled with the site and the FYRR inputs already entered.
- **The Schemes view** (the header's fifth view, PLAN-009):
  - A list with name, measure, completed date, status and result, sortable.
  - The selected scheme's page shows:
    - details, which can be edited;
    - collisions by year, with the works period shaded and before/after marked;
    - the result card;
    - FYRR, expected against achieved;
    - links to the site page.
- **Map layer:** scheme footprints, coloured by result, toggled like the other layers.
- **Monitoring report PDF:** the scheme page in the site-PDF frame, with the method stated.
- **Export and import** of all schemes as one JSON file: a portable copy outside the database.

## 5. API

| Endpoint | Purpose |
|---|---|
| `GET /api/schemes` | List with status and headline result |
| `POST /api/schemes` | Create |
| `GET`, `PUT`, `DELETE /api/schemes/{id}` | Read, edit and delete |
| `GET /api/schemes/{id}/evaluation` | The result (§3), cached per data load |
| `GET /api/reports/scheme.pdf?id=` | Monitoring report |
| `GET /api/schemes/export`, `POST /api/schemes/import` | JSON copy |

**Writes, kept safe:**
- The API's database role stays read-only by default (PLAN-006 C4). It gains `INSERT`/`UPDATE`/`DELETE` on `app.*` only, and write handlers open their transaction with `READ WRITE`. A bug elsewhere still can't change the published data.
- Write requests must carry `Content-Type: application/json` and an `Origin` matching the site. That blocks cross-site form posts (CSRF) from other pages open in the same browser.
- All input is validated with pydantic models, the geometry is checked for size and validity, writes are rate-limited (as `/api/client-errors` is), and each write is logged with its request ref.

## 6. Backups (before V5 goes live)

- The weekly full dump already includes any new schema. Add a **daily dump of `app` only**: small, kept for 30 days.
- Point `BACKUP_DIR` at the NAS (the NFS mount in DEPLOY.md → Backups).
- **Restore test:** restore the `app` dump into a scratch database on the Mac and check that the schemes come back.
- Document all of this in DEPLOY.md, and add "last `app` backup" to `diagnose.sh`.

## 7. Phases (each a PR)

| Phase | Content | Size |
|---|---|---|
| S1 | `app` schema and migration (organisation-aware: `org_id` on every table), role grants, CRUD API with the write safeguards, daily `app` backup, tests (including the role: writes succeed on `app` and fail everywhere else) | 1½ days |
| S2 | "Save as scheme" from site pages and selections; Schemes view with list and page (details, by-year chart); FYRR inputs carried over | 2 days |
| S3 | Evaluation: yearly calibration factors, EB (A) and comparison group (B), CIs, status. Unit tests on worked examples from Hauer, plus synthetic sites with a known effect | 2½ days |
| S4 | Result card and map layer; monitoring report PDF; JSON export and import; docs and FOLLOWUPS | 1½ days |
| — | BOSGAME: backups to the NAS and a restore test, before S2 is used for real | you, ½ hour with me |

## 8. Risks

- **Too little after-data.** Most schemes have 1–2 years of after-data for a long time. The result says "not enough evidence yet" rather than showing a misleading percentage, and the CI makes that visible.
- **Model drift.** The safety models are refitted on the latest five years at every load. A scheme's evaluation is recomputed per load, so its result can move a little. The report gives the data load it used.
- **Treated sites in the comparison group.** Other schemes in the comparison area bias method B slightly. Later, exclude recorded schemes' footprints from the comparison area.
- **Selection bias:** sites chosen *because* they had a bad year are exactly what EB corrects for. Method B can't, and says so.

## 9. Decisions (agreed 2026-10-09, all as recommended)

- **D1:** all five site types in the first version.
- **D2:** the proposed 11 measures plus "other". Rename them later if your authority uses different ones; stored values are keys, so labels can change.
- **D3:** 3 years before and 3 after by default, leaving out the works; 1–5 allowed.
- **D4:** anyone who can open the app can edit; edits are stamped with the Access email or "LAN".
- **D5:** the comparison area is the rest of the same highway authority, on the same road classes.

The questions as asked:


- **D1 — Site types in the first version:** junction, link, cluster, route section and drawn area, all at once (recommended; the drawn area covers 20 mph zones), or sites only first?
- **D2 — Measure list.** Proposed:
  - traffic signals (new or upgraded)
  - roundabout or mini-roundabout
  - junction layout or priority change
  - pedestrian or cycle crossing
  - speed limit change
  - traffic calming
  - surfacing / anti-skid
  - signing and lining
  - street lighting
  - safety camera
  - other

  Add or rename to match your authority's usual categories.
- **D3 — Default periods:** 3 years before and 3 after, leaving out the works (recommended), with 1–5 allowed for each?
- **D4 — Who can edit:** anyone who can open the app, that is you remotely through Access and anyone on your home LAN, with edits stamped "LAN" or the Access email. Fine as a single-user tool (recommended), or should LAN access be read-only for schemes?
- **D5 — Comparison area for method B:** the rest of the same highway authority on the same road classes (recommended), or the authority's similar authorities from V4?

## 10. As built

### S1 (2026-10-09)

**Migration `007_app_schemes.sql`:**
- Creates `app.org`, holding the one default organisation, and `app.scheme`, as in §2.
- Adds to `app.scheme`:
  - `org_id`;
  - `version`, for optimistic locking: an edit must name the version it started from, or it gets a 409;
  - soft deletion (`deleted_at` and `deleted_by`), so a mistake can be undone.
- Names are unique per organisation, ignoring case, among live schemes.

**The API role's rights on `app`:**
- `SELECT` on all `app` tables.
- `INSERT` on `app.scheme`.
- `UPDATE` only on the columns an edit can change: never `id`, `org_id` or `created_*`.
- No `DELETE`.

**Schemes API: `stats19.api.schemes`.** Every query is scoped by `stats19.api.org.current_org`, which returns the default organisation until accounts exist (PLAN-014 C2).
- `GET /api/schemes/options`: the measures (codes and labels) and site types.
- `GET /api/schemes`: the list, without geometry, with a label point.
- `GET`, `PUT` and `DELETE /api/schemes/{id}`, and `POST /api/schemes`.

**Input checks:**
- **Footprint against site type:** junctions, clusters and areas are polygons; links and routes are lines.
- **GeoJSON nesting:** checked, with at most 20,000 points.
- **Footprint shape:** valid, inside GB, at most 25,000 km² (Wales) or 500 km.
- **Works dates:** in order, and between 1979 and ten years ahead.
- **Periods:** 1–5 years.
- **FYRR snapshot:** its fields and ranges.
- **Unknown fields:** refused.

**Write safeguards: `stats19.api.writes`.**
- `check_write`:
  - same-site `Origin`, compared with `Host`;
  - a JSON body for POST and PUT;
  - a global limit of 120 writes per 5 minutes.
- `read_write`: opens the request's first transaction as `READ WRITE`, and refuses otherwise.
- `editor`: the Access email, or "LAN".

**Backups:** a daily dump of `app` to `BACKUP_DIR/app`, keeping 30. Tested by backing up and restoring into a scratch database (DEPLOY.md → Backups).

**Tests:**
- `tests/test_schemes.py`: the API and its checks.
- `tests/test_api_role.py`: the role writes only what it should, and only in READ WRITE; the API works end to end as the read-only role.


### S2 (2026-10-10)

**"Save as scheme"** opens one form (`web/src/components/schemes/SchemeForm.tsx`) from:
- **Junction pages:** the footprint is the junction's match area, its OS shape buffered by 25 m (`match_area`, now returned by `GET /api/junctions/{id}`). This is the ground its collisions are matched within. An early version used a 25 m circle round the centre point, which missed most collisions at big junctions.
- **Road pages:** the stretch of OS links the count covers (DfT's link if there's no stretch). Collisions within 25 m of the line count, the radius the link matching uses.
- **Cluster sites:** the site's circle. Ranks change with every run, so no site id is kept.
- **Routes:** the corridor's links within the selected area, as one line.
- **Area:** a drawn circle or shape, or an authority's boundary as the map draws it (simplified to 25 m).

**The form:**
- Name (the site's title by default), measure, works start and end, years before and after, cost, description.
- **The expected reduction**, when the site has an FYRR basis:
  - Junctions and roads use the Empirical Bayes estimate.
  - Clusters use their own record.
  - Routes and areas have none.
- **What's typed into the site's FYRR calculator is carried over:** the cost and the reduction.
- The form checks what it can before sending. The server's reasons are shown when it refuses.

**The Schemes view** (fifth header tab; `?view=schemes&sc=<id>`):
- **The list**, sorted by status (default), completed date, name or measure. Each row shows its stage.
- **A scheme's page** uses the site-page skeleton. It has:
  - figures: completed, months of after-data, cost, expected FYRR;
  - collisions by year, with the before, works and after periods shaded, and part-years hatched;
  - details, with Edit and Delete (Delete is confirmed inline);
  - the expected return;
  - links to the site as it is today, and a zoom to the footprint, which also happens when the page opens.

**API additions:**
- Each scheme carries `status`:
  - `stage`: `undated`, `in_works`, `monitoring` or `complete`;
  - `after_months` of `after_months_wanted`;
  - `data_end`: 31 December of the latest loaded year.
- `GET /api/schemes/{id}/collisions` gives:
  - the by-year counts in the footprint (inside an area, or within 25 m of a line);
  - the before and after periods;
  - the match rule.
- The periods are pure functions in `stats19.api.scheme_periods`, unit-tested and ready for S3.
- The largest footprint area was raised from 25,000 to 40,000 km². Highland, the largest authority, is about 26,000 km².

**Dev fix:** Vite's dev proxy now keeps the browser's `Host`. Before, every write failed the same-site check under `npm run dev`. Production (Caddy) wasn't affected.

Limits and next steps are in FU-057.

### S3 (2026-10-10)

**The maths, in `stats19.evaluation`.** These are pure functions, tested in `tests/test_evaluation.py`.
- **Periods:**
  - year fractions by day, for part-years;
  - clipping a period to the loaded data.
- **Calibration:**
  - yearly calibration factors (observed ÷ predicted for the peer group);
  - a period's μ from the yearly SPF and those factors.
- **Method A (Empirical Bayes):** Hauer's before/after for one site, and for a group (Σλ, Σπ, ΣVar π).
  - Without collisions after, the upper limit uses the Poisson bound.
- **Method B (comparison group):** a log odds ratio CI, with Haldane's correction when a count is zero.
- **The verdict and wording:**
  - "fewer", "more", "no evidence yet", or "too early" below 12 months of after-data;
  - method B's wording warns about regression to the mean.
- **Tests:**
  - worked examples, worked by hand in the docstrings;
  - 40,000 synthetic sites, the worst before-records "treated". EB recovers a true 30% effect, and no effect, within 0.03, while a naive before/after overstates the benefit by more than 15 points.

**Calibration, in the safety build (`stats19.reference.safety_calibration`).**
- New table `geo.safety_calibration`: per peer group and year, the group's observed collisions ÷ its predicted collisions for a year. It covers the years the collision matches cover (the last 10), and is rebuilt with the models at every load.
- **On the full data:**
  - Junction groups average 1.00 over the model years, as they should.
  - Link groups average about 0.9: the NB fit weights busy sites less, so its predictions sum a little above the counts. The factor corrects that level, which is what HSM calibration is for.
  - 2020 shows the COVID drop: 0.85 across all groups.
- A year before the factors begin borrows the earliest; the newest year, before its counts are in, borrows the latest.

**`GET /api/schemes/{id}/evaluation` (`stats19.api.scheme_evaluation`).**
- **Counting:** collisions in the stored footprint, by date, over the before and after periods; the after period is clipped to the loaded data.
- **Which collisions (FU-057, agreed 2026-10-10: like for like):**
  - a junction scheme counts only the collisions STATS19 records at a junction, as the junction page and its model do;
  - a link scheme counts the rest;
  - every other scheme counts all of them.
  - The S2 by-year chart now uses the same rule (`schemes.counted`), so the chart and the result agree. Its subtitle says which collisions it counts.
- **Method A (EB)** when the scheme's junction or link has a safety model today. μ for each period is the site's prediction a year × each year's calibration factor. The response gives μ_B, μ_A, EB_B, α and the factors used.
- **Method B (comparison group)** otherwise, with the reason given in words:
  - **The comparison area** is the rest of the highway authority the footprint is in, on the road classes of the scheme's collisions (D5).
  - **If the footprint is more than half its authority** (an authority-wide 20 mph scheme, say), the rest of Great Britain stands in.
  - **Collisions within the footprint** are left out of the comparison.
- **The response:**
  - stage and months of after-data, the clipped periods, and the method with its reason;
  - counts before and after, with KSI shown descriptively;
  - θ with its 95% CI and the % change, collisions expected and seen after, and collisions saved a year;
  - the verdict and headline;
  - the saving valued at the scheme's own FYRR price, with the achieved and expected FYRR.
  - **Without a result,** a message says why: no works dates, works not finished, no after-data yet (with when DfT publishes it), the before period earlier than the data, or no collisions to compare.
- **Cached** per data load and scheme version, in process.
- **Checked on the full data:**
  - Each evaluation took under 0.1 s: a busy signalised junction, a motorway link, a 1 km area in Hackney, and a junction with no model.
  - Junction footprints count within 1% of the junction model's own matching: 1,312 against 1,296 over 500 sample junctions.
  - Link footprints count about 8% more than the model's: 2,857 against 2,637 over 300 sample links. Slip roads and parallel roads within 25 m are the likely cause. See FU-059.
- **Tests:**
  - `tests/test_safety_calibration.py`;
  - `tests/test_scheme_evaluation.py`, which checks the endpoint against `stats19.evaluation` on synthetic collisions. It covers EB with a trend, the comparison group, the junction rule, every "no result" reason, "too early", and the cache.

**For S4:** the result card on the scheme page (this endpoint is ready for it), the map layer coloured by result, the monitoring report PDF, and JSON export and import.
