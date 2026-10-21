# PLAN-002 — Collision signatures: proxies for contributory / road safety factors

- **Status:** REJECTED 2026-10-05: not implementing; kept as a research record (see FU-001 for reasons)
- **Raised by:** FU-001
- **Branch:** `plan/fu-001-collision-signatures`
- **Depends on:** PLAN-001 (core tables), FU-004 (harmonised historic codes), FU-005 (marts rebuilt after swap)

## 1. What the research found

### Contributory factors → road safety factors
- Following the latest STATS19 review, **contributory factors (CFs) are being replaced by road safety factors (RSFs)**. Some forces began switching in late 2023; the rollout is phased, and police forces moved at different times.
- **RSFs:** officers attending the scene pick **up to 6 from 35**, each marked as very likely (A) or possible (B), and linked to a vehicle or casualty. The 35 factors fall into six groups ([STATS20 2024 spec, Annex 4](https://assets.publishing.service.gov.uk/media/6925a35433d088f6d5da2cf0/STATS20_2024_specification.pdf)):

  | Group | Codes | Examples |
  |---|---|---|
  | Behaviour / inexperience | B1–B8 | Disobeyed signal, poor turn, ineffective observation, learner, passing too close, door opened, sudden braking |
  | Distraction / impairment | D1–D7 | Alcohol, drugs, fatigue, eyesight, illness, mobile device, distraction |
  | Non-motorised road users / PPT | P1–P5 | Misuse of crossing, entering from pavement, pedestrian risk-taking, careless, hard to see |
  | Road | R1–R5 | Defective surface, slippery, view obscured by parked vehicles or vegetation, dazzle / weather |
  | Speed behaviour | S1–S5 | Exceeding limit, too fast for conditions, crime, aggressive, too slow |
  | Vehicle | V1–V5 | Tyres, defects, overloading, blind spot, lights |

- **Not in the open data.** CF/RSF are classed as *sensitive fields*. DfT publishes them only as **GB-level** tables (RAS0701–0703, plus a new RAS0701 *split* table, September 2026). The **local authority table RAS0706 is no longer updated**, so there is currently no published local breakdown at all ([data tables](https://www.gov.uk/government/statistical-data-sets/road-safety-statistics-data-tables)).
- **Collision-level factors can be requested** from DfT via the sensitive data form (roadacc.stats@dft.gov.uk). This is the only way to *validate* proxies at collision level. → Decision D1.
- **Mixed coding:** CF and RSF data are mixed by force and year, and the change itself shifts the distributions (speed-related factors fall, non-motorised user factors rise). Any trend in "factor" shares across 2023–2026 is partly an artefact of the change ([2024 spec impacts](https://www.gov.uk/government/publications/stats19-collection-and-use-impacts-of-the-2024-specification/stats19-collection-and-use-initial-impacts-of-transition-to-the-2024-specification), [Transport Scotland RSF chapter](https://www.transport.gov.scot/publication/reported-road-casualties-scotland-2024/road-safety-factors-previously-contributory-factors/)).

### Speed: your example
- **Speed limit — yes**, one per collision: the *permanent* limit, even where a temporary limit applied.
- **Estimated vehicle speed — no.** STATS19 records no speed for any vehicle. Speed appears only as a subjective RSF (S1 exceeding the limit, S2 too fast for conditions), and that's in the withheld data.
- **What we can infer about speed** is limited to signatures associated with excessive speed:
  - single-vehicle loss of control;
  - skidding or overturning;
  - leaving the carriageway and hitting a fixed object;
  - higher severity than is typical for the speed limit and road context.

  These are **associations, not measurements**, and the plan labels them that way.

### Proxy field completeness (measured on our core tables, % of vehicles with a usable value)

| Era | First point of impact | Manoeuvre | Direction from/to | Skidding | Driver age | Engine cc |
|---|---|---|---|---|---|---|
| 1979–84 | 73–92 | 100 | 73–92 | 75–92 | 94 | 0 |
| 1985–2014 | 98–100 | 100 | 99–100 | 100 | 89–94 | 10–74 |
| 2015–19 | 98.5 | 97.6 | 96.4 | 97.5 | 88 | 75 |
| 2020–25 | 94 | 90 | 89 | 90 | 85 | 75 |

The proxies are usable for roughly 1985 onwards; 1979–84 is thinner. Pre-2024 manoeuvre codes include **"going ahead on left/right-hand bend"** (historic codes 16/17), a bend signal that the 2024 coding dropped.

## 2. Approach

Derive **collision signatures** from objective, published fields, using transparent rules. Each signature declares:
- which RSF it approximates,
- a confidence level (high / medium / low),
- the years it is valid for.

The rules live in a config table, so you can add or tune them without code changes, and every result can be traced to a rule.

These signatures replace the "type" filters you described (shunts in the wet, dark crashes, etc.). They also feed hotspot analysis (PLAN-003), which can cluster any signature × condition × period combination.

## 3. Signatures

### A. Manner of collision: what physically happened (high confidence)

Built per **vehicle pair** from:
- relative heading: compass `direction_from` → `direction_to`, at 45° resolution;
- each vehicle's `first_point_of_impact`;
- each vehicle's `vehicle_manoeuvre`.

| Signature | Rule sketch |
|---|---|
| **Rear-end / shunt** | Same heading (±45°); striker impact = front, struck impact = back; struck manoeuvre ∈ {slowing/stopping, waiting to go ahead, held up, going ahead, moving off} |
| **Queue shunt** | Rear-end where the struck vehicle was stationary (waiting / held up / slowing) |
| **Head-on** | Opposite headings (180° ± 45°); both impacts front |
| **Angle / T-bone** | Headings ~90° apart; one front impact into the other's offside/nearside; usually at a junction |
| **Turning across path** | Angle or head-on where one vehicle is turning right / waiting to turn right / U-turn |
| **Sideswipe / lane change** | Same heading; side impacts; manoeuvre ∈ {changing lane, overtaking} |
| **Overtaking conflict** | Any pair where one vehicle is overtaking (codes 13–15) |
| **Reversing** | Any vehicle reversing |
| **Parked-vehicle strike** | Struck vehicle parked, or `hit_object_in_carriageway` = parked vehicle |
| **Dooring** | `hit_object_in_carriageway` = open door (≈ RSF B7) |
| **Single-vehicle** | `number_of_vehicles = 1` (subtypes in B) |
| **Pedestrian** | Casualty class = pedestrian, with the pedestrian movement code (e.g. crossing from nearside, masked by a parked vehicle ≈ R3) |

Collisions with three or more vehicles get a primary type (the first pair, by `vehicle_reference`) plus a multi-vehicle flag. Where the geometry is ambiguous, the type is `unclassified`; it is never guessed.

### B. Loss of control: a proxy for speed or conditions (medium confidence)

| Signature | Rule sketch | Approximates |
|---|---|---|
| **Single-vehicle loss of control** | One vehicle; skidded / overturned / jackknifed, **or** left the carriageway, **or** hit a fixed off-carriageway object | S2 too fast for conditions, R2 slippery |
| **Run-off on bend** | Loss of control and historic manoeuvre 16/17 (pre-2024 only) | S2 |
| **Loss of control in wet/ice** | Loss of control and surface ∈ {wet, snow, frost/ice, flood} | R2, S2 |
| **Cross-over** | Left offside and crossed the central reservation | S2 / S4 |
| **Fixed-object severity** | Hit a tree, pole, lamp post or wall (high injury risk) | — |

### C. Conditions and environment (high confidence: recorded directly)

- **Light:** daylight / dark-lit / dark-unlit / dark-no-lighting.
- **Surface:** wet, ice, snow, flood. **Weather:** rain, snow, fog, high winds.
- **Carriageway hazards / special conditions** (≈ R1): roadworks, defective signals, oil, potholes.
- **Road context:** road class, road type, speed limit band, urban/rural, junction detail and control, pedestrian crossing.
- **Time:** night (by time *and* by darkness), weekend, peak commute, school run, season.

### D. Road users and vehicles (high confidence: recorded directly)

- **Vulnerable users:** pedestrian, cyclist, motorcyclist (by cc band), e-scooter / PPT, horse rider.
- **Vehicle features:** HGV/LGV, bus, towing/articulated, left-hand drive (≈ B5 "unfamiliar with driving on the left").
- **Drivers:** young (17–24), older (75+), journey purpose (work, commute, blue-light), driver home distance banding (≈ unfamiliarity with the area, B5).

### E. Inferred risk patterns (low–medium confidence; the clearly labelled "inference" layer)

| Signature | Rule sketch | Approximates | Basis |
|---|---|---|---|
| **Impairment surrogate** | Single-vehicle collision with a male driver, 22:00–04:00, especially weekends | D1 alcohol / D3 fatigue | Long-standing proxy used in drink-drive research when breath-test data are missing |
| **Fatigue surrogate** | Single-vehicle run-off on motorway / dual carriageway at 02:00–06:00 or 14:00–16:00 | D3 | Sleep-related collision definitions (TRL) |
| **Low-sun dazzle** | Sun elevation < 15° and sun azimuth within ±30° of the vehicle's heading (`direction_to`), daylight, not raining | R5 | Computed per vehicle from date, time and location |
| **Excess severity** | KSI share at a site or segment significantly above the expected share for its speed limit × road type × urban/rural × user mix | S1/S2 at site level | Severity-as-speed proxy; the site-level indicator for hotspots |
| **Observation failure at junctions** | Angle / turning-across-path collision at a give-way or uncontrolled junction where the striking vehicle is entering the main road | B4 / B3 | Classic "looked but failed to see" configuration |

What can't be inferred, and won't be attempted: mobile phone use (D6), eyesight (D4), vehicle defects (V1/V2/V5), crime (S3), aggression (S4), whether the limit was exceeded (S1). The plan states these explicitly as gaps.

## 4. Data model (`mart` schema, rebuilt after each core swap)

| Object | Grain | Contents |
|---|---|---|
| `mart.vehicle_harmonised` | vehicle | `*_harmonised` codes, using `lookup_conversion` to map historic → 2024 codes (FU-004) |
| `mart.vehicle_pair` | ordered vehicle pair in a collision | relative heading (0/45/90/135/180°), impact pair, manoeuvre pair, derived pair type |
| `mart.signature_rule` | rule | id, name, group (A–E), SQL predicate, approximates_rsf[], confidence, valid_from/to_year, description |
| `mart.collision_signature` | collision × signature | long table: one row per signature that matched (for filtering) |
| `mart.collision_features` | collision | wide row with the primary manner of collision, boolean flags, and decoded conditions, for map filtering and export |

The rules are applied by Python, which composes each `signature_rule.sql_predicate` into one `INSERT … SELECT` per rule. The predicates are reviewed SQL in the repo (`src/stats19/sql/marts/rules/*.sql`), never user input. Low-sun dazzle needs a solar-position function: either a small SQL function (NOAA algorithm) or vectorised in Python. I'll benchmark both.

## 5. Validation

1. **Unit fixtures per rule:** hand-built collisions that must, and must not, match.
2. **Plausibility against published aggregates:** compare the signature shares by year and road class with GB RAS0701/0703 factor shares, e.g. the loss-of-control share vs the S2 share, and the impairment surrogate vs the D1 share. We expect directional agreement, not equality.
3. **Manual review:** a 200-collision random sample per major signature, where you judge from the decoded fields.
4. **Gold standard (if D1 = yes):** with DfT's collision-level CF/RSF data, measure each rule's precision and recall and tune it, then publish the confusion matrix in `docs/`.
5. **Specification-change guard:** report signatures separately for the 2011 and 2024 coding (by year and force), and flag any rule that depends on a recoded field.

## 6. Phases

| # | Work | Complexity |
|---|---|---|
| 1 | FU-004 harmonised codes view; vehicle-pair table | Medium |
| 2 | Signature rules A (manner) + C/D flags; `collision_features` | Medium |
| 3 | Rules B (loss of control) + E (inference layer, incl. solar position) | Medium–high |
| 4 | Validation: fixtures, aggregate comparison, sample review | Medium |
| 5 | Marts rebuilt automatically after each core swap (FU-005); validation checks for mart row counts | Low |

## 7. Risks

- **HIGH — proxies get read as causes.** Mitigation: the naming says "signature" or "pattern" (never "cause"), every output carries a confidence label, and docs and UI show caveats.
- **MEDIUM — 2024 recoding breaks rules** (manoeuvre, junction detail). Mitigation: harmonised codes, and a per-rule `valid_from/to`.
- **MEDIUM — direction data missing (~10% since 2020).** Mitigation: fall back to impact + manoeuvre only, marked as lower confidence.
- **LOW — performance:** pair table ≈ 16 M rows. Fine on Postgres; built once per release.

## 8. Decisions needed from you

- **D1** — Request collision-level CF/RSF data from DfT (sensitive data form) to validate the proxies? Recommended: yes. It's free to ask, it turns guesses into measured accuracy, and the terms will say whether it can sit on your home lab.
- **D2** — Include the inference layer (E) in phase 1, or ship the factual signatures (A–D) first? Recommended: A–D first, E behind a flag.
- **D3** — Any signatures you specifically want that aren't listed (e.g. from your KeyAccident usage)?
