# PLAN-001 — Automated STATS19 backend pipeline

- **Status:** Approved 2026-10-05, in progress
- **Branch:** `feat/pipeline-foundation`
- **Scope:** Phases 1–5 (Phase 6 marts / hotspots and Phase 7 frontend get their own plans)

## Goal

Automatically ingest the full STATS19 history (1979–latest) from the Department for Transport (DfT), load it into PostgreSQL + PostGIS with correct types and enforced keys, validate every load, and run it unattended on the home lab.

## Source facts (verified 2026-10-05)

| Item | Detail |
|---|---|
| Landing page | https://www.gov.uk/government/statistics/road-safety-data |
| Change signal | GOV.UK content API `https://www.gov.uk/api/content/government/statistics/road-safety-data` → `public_updated_at` |
| Full history files | `https://data.dft.gov.uk/road-accidents-safety-data/dft-road-casualty-statistics-{collision,vehicle,casualty}-1979-latest-published-year.csv` (~1.5 GB / 1.8 GB / 1.0 GB) |
| HTTP | No ETag / Last-Modified, Range ignored, HEAD returns bogus length → change detection = content API timestamp + SHA-256 of downloaded file |
| Data guide | `.xlsx` with sheets `2024_code_list` (table, field name, code, label, note) and `2011_to_2024_conversion` |
| Release cadence | Final annual data late July; provisional Jan–Jun data late November; ad-hoc corrections |
| Keys | `collision_index` (was `accident_index`), `collision_year`, `collision_ref_no` (text, leading zeros) |
| Missing data | `-1` = missing/out of range, blank = null (e.g. pre-1999 lat/lon) |

## Architecture

```
DfT ──► download (Python, httpx, SHA-256) ──► raw.*       all TEXT, header-driven
                                               │ COPY FROM STDIN
                                               ▼
                                            build.*      typed, keyed, geometry; rejects → quarantine
                                               │ validation gates (etl.run_check)
                                               ▼  atomic schema swap
                                            core.*       collision / vehicle / casualty
                                            lookup.*     code list + 2011→2024 conversion
                                            etl.*        run history, files, checks
```

- **Database:** PostgreSQL 17 + PostGIS 3.5 (`imresamu/postgis`, multi-arch amd64/arm64).
- **Pipeline:** Python 3.12, `psycopg` 3 (COPY streaming), `httpx`, `openpyxl`. Memory use stays flat because nothing is loaded into a dataframe.
- **Idempotent:** each run rebuilds `build`, validates it, then swaps it in as `core`. A failed run leaves `core` untouched.
- **Keys:**
  - `core.collision` PK `collision_index`
  - `core.vehicle` PK `(collision_index, vehicle_reference)` → FK collision
  - `core.casualty` PK `(collision_index, casualty_reference)` → FK collision, FK `(collision_index, vehicle_reference)` → vehicle
- **Types:**
  - Coded fields → `smallint`; `-1` kept as a code because it has a label.
  - Measures (ages, engine cc, coordinates) → `-1` becomes `NULL`.
  - `date` + `time` → `collision_date`, `collision_time`, `collision_datetime`.
  - `geom_bng` `Point/27700` from easting/northing; `geom_wgs84` `Point/4326` from lon/lat, or transformed from BNG when lon/lat is missing.

## Phases

1. **Foundations:** repo layout, `pyproject.toml` (uv), Docker Compose, legacy SQL archived in `legacy/`.
2. **Extract:** content-API check, streamed download + SHA-256, data-guide parser → `lookup.*`, header drift detection.
3. **Load + transform:** `raw` COPY, typed `build` tables, quarantine for duplicates and orphans, atomic swap.
4. **Validation gates:** row-count regression, quarantine ratio, year coverage, GB bounding box, vehicle/casualty count consistency, lookup coverage.
5. **Schedule + deploy:** cron container, backups, runbook for the home lab.

## Hosting recommendation (home lab)

- **Database → BOSGAME E2** (x86, 16 GB, NVMe), next to Forgejo / Portainer.
  - Full history is about 4.3 GB of CSV, roughly 12–15 GB in Postgres with indexes.
  - PostGIS clustering over ~15 M rows wants more CPU than a Pi 5 has.
- **Alternatives:** the Pi 5 (already a DB host, arm64 image works, but slower for spatial clustering), or the NAS app pool (Pentium; busy with media).
- **Pipeline container:** same host as the DB, to avoid shipping gigabytes over the LAN.
- See FU-003.

## Risks

- **HIGH — schema drift by DfT.** Mitigation: header checks against `EXPECTED_COLUMNS`, unknown columns logged, missing ones fail the run.
- **MEDIUM — historic coding differences.** Mitigation: `*_historic` columns kept verbatim, plus the conversion sheet loaded into `lookup.conversion`.
- **MEDIUM — full-history volume on modest hardware.** Mitigation: streaming COPY, unlogged build tables, indexes created after load.
- **LOW — collision "type" is not in the data.** It will be derived in Phase 6 (FU-001).
