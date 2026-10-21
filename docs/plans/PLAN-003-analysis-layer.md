# PLAN-003 — Analysis-ready layer (`mart`)

- **Status:** DONE 2026-10-05 (D1 = no gap-filling, D2 = by year only). Results in the Outcome section at the end
- **Branch:** `feat/analysis-layer` (stacked on PR #2)
- **Covers:** FU-002, FU-004, FU-005, FU-007, FU-009. FU-006 is deferred to the November release.

## Goal

Add a decoded, cross-year-consistent, validated layer that the frontend slicers and exports can query directly.

- Every coded value has a label.
- Every field shows honestly which years it is populated for.
- The layer is rebuilt and checked atomically with each release.
- Nothing is derived or inferred beyond what is recorded (the FU-001 principle).

## Evidence gathered (run 2 data, 2026-10-05)

### FU-004: DfT has already harmonised the 2024-coded fields
DfT back-fills the new-coded columns for **all historic years**. Where both the new and historic columns are present, the new value equals the conversion of the historic one in **every row checked**:

| Field | Rows checked | Agree |
|---|---|---|
| `vehicle_manoeuvre` | 15,988,509 | 100% |
| `junction_detail` | 8,955,307 | 100% |

`pedestrian_crossing` and `carriageway_hazards` merge two and three old fields respectively, and are also fully back-filled (≥97% populated in every era).

The remaining gaps are where DfT left the new column blank:

| Field | Rows | Years | Historic value | Assessment |
|---|---|---|---|---|
| `vehicle_location_restricted_lane` | 8.24 M | 1979–1998 | 98% code 0 "main carriageway" | Looks like a recording default; DfT deliberately didn't convert it |
| `journey_purpose_of_driver` | 1.36 M | 2005–2010 | code 15 "Other/Not known" | Not in the conversion sheet; DfT maps "Other" and "Unknown" separately to 6 |
| `junction_detail` | 12,885 | to confirm | mappable | Small; to investigate |

**So FU-004 needs no new harmonisation logic.** The 2024-coded column *is* the harmonised field, and the `*_historic` columns are kept for extra detail (e.g. the bend codes 16/17). See decision D1 on gap-filling.

### FU-009: missing labels
| Code | Rows | Evidence | Proposed label |
|---|---|---|---|
| `casualty_type = 33` | 6,103 | 2020–2025; linked vehicle is always `vehicle_type = 33`, "Personal powered transporter" | "Personal powered transporter (e.g. e-scooter) rider or passenger" |
| `collision_injury_based = -1` | 6.0 M | Rows from before injury-based reporting | "Not applicable (before injury-based reporting)" |
| `casualty_injury_based = -1` | 8.0 M | Same | Same |

### FU-002: guide names vs CSV headers
After the two aliases, run 2 reports **no** field-name mismatches. The only unlabelled codes left are the FU-009 ones. → Close it, adding a permanent check so future drift is caught.

### FU-007: thresholds
Runs 1 and 2 had: quarantine 0 after FU-008, parse failures 0, row counts identical. Releases add ~100k collisions a year, and DfT revisions are small.

## Design

### 1. Lookups (FU-009, FU-002)
- New file `src/stats19/sql/lookup_supplement.csv` with columns `table, field, code, label, note`. Each row cites its evidence in `note`.
- `lookup_code` gains a `source` column (`dft_guide` | `supplement`). The guide always wins if it later adds the same code.
- New warn check `guide_field_unmatched`: any field the guide lists that has no CSV column.

### 2. `mart` schema, rebuilt atomically with `core` (FU-005)
- Built in a `build_mart` schema during the same run, after `build` and before validation.
- The swap renames both schemas in **one transaction** (`core→core_previous`, `mart→mart_previous`, `build→core`, `build_mart→mart`), so the marts can never point at stale tables. This solves the view/OID problem.
- Each object is defined by a SQL file in `src/stats19/sql/marts/`.

| Object | Kind | Grain | Contents |
|---|---|---|---|
| `mart.collision` | table | collision | All core columns, plus **recorded** aggregates from child rows: casualties by severity (fatal/serious/slight and adjusted), casualties by road-user type, vehicles by type group (pedal cycle, motorcycle, car, bus, goods, PPT, other), `involves_pedestrian` / `_cyclist` / `_motorcyclist` / `_hgv` / `_ppt` flags, youngest and oldest driver age. These are counts of what was recorded, not inference. |
| `mart.collision_decoded` | view | collision | `mart.collision` plus a `<field>_label` column for every coded field (generated from the column spec) |
| `mart.vehicle_decoded`, `mart.casualty_decoded` | view | vehicle / casualty | Core columns plus labels |
| `mart.field_catalog` | table | field | table, field, kind (code/measure/text/date), description (guide notes), first and last year populated, % populated per year (JSON), harmonisation note. This powers slicer UI hints such as "recorded from 2005". |
| `mart.code_counts` | table | field × code × year | Counts per code per year, for slicer option lists with counts and for quick trend charts |

The labels are views over code columns rather than stored text, to save space; a decoded copy of every row would roughly double the database size. If query speed needs it later, specific views can be materialised.

### 3. Validation (FU-007)
- **Tightened, based on runs 1–2:**
  - `quarantine_ratio` ≤ 0.1%
  - `parse_failures` ≤ 0.01%
  - `row_count_vs_previous` ≥ 0.99
- **New mart checks:**
  - mart row counts equal core
  - the aggregate casualty count per collision matches `number_of_casualties` (already 0.0%)
  - `field_catalog` covers every spec column
- `unlabelled_codes` **stays a warning**, so a new DfT code (like 33) never blocks a release; it is reported for a follow-up.

## Phases (TDD throughout)

| # | Work | Size |
|---|---|---|
| 1 | Supplement labels, `source` column, `guide_field_unmatched` check; close FU-002 and FU-009 | S |
| 2 | Mart build framework: `build_mart`, dual-schema atomic swap, SQL-file runner; close FU-005 | M |
| 3 | `mart.collision` aggregates, decoded views, `field_catalog`, `code_counts` | M |
| 4 | Threshold tightening and mart checks; close FU-007 | S |
| 5 | Full real rebuild; record timings, sizes and check results; close FU-004 with the evidence above | S |

## Risks

- **MEDIUM — mart build time.** Aggregating 16 M vehicles and 12 M casualties adds roughly 5–10 min per run. This is acceptable for 2–3 runs a year; I'll measure it in phase 5.
- **LOW — decoded views over ~80 lookup joins.** Mitigation: a per-field lookup CTE using hash joins; filtered queries only decode the rows they return.
- **LOW — supplement labels later contradicted by DfT.** Mitigation: the guide wins, and the `source` column shows provenance.

## Decisions (resolved 2026-10-05: D1 = no, D2 = by year only)

- **D1 — Fill DfT's gaps from the historic codes?** Recommended: **no**. Use DfT's harmonised columns as they are; `field_catalog` shows the gaps honestly (e.g. "restricted lane recorded from 1999"). Filling 1979–98 restricted lane would mostly inject a probable default ("main carriageway"), and mapping journey-purpose code 15 would merge "other" into "not known". This follows the same principle as FU-001.
- **D2 — `mart.code_counts` by year only, or by year × police force / local authority as well?** Recommended: by year now, adding geography when the frontend needs it.

## Outcome (run 3, 2026-10-05, MacBook M1 Max)

| | |
|---|---|
| Run time | 20.5 min total. Mart build: `collision_summary` 1 min, `field_catalog` 4 s, `code_counts` ~7 min (FU-012) |
| Checks | All blocking checks pass. Unlabelled codes 0, guide fields unmatched 0, road-user codes unmapped 0, `field_catalog` 100/100 fields. Only warning: 0.2% of collisions have no location |
| Size | Database 15 GB with marts. `collision_summary` 1.4 GB after the smallint casts (3.05 GB before) |
| Query | README example (dark + wet + motorcycle, 2020–25, decoded): 0.27 s. Single decoded collision: 2 ms |
| Tests | 80 passing, 93% coverage |
