# Data model

How the database is organised: what each schema holds and where every reference dataset comes from. For the overview, see the [README](../README.md).

## Core schema (`core`)

| Table | Key | Notes |
|---|---|---|
| `collision` | `collision_index` | `collision_date`, `collision_time`, `collision_datetime`, `geom_bng` (EPSG:27700), `geom_wgs84` (EPSG:4326), `geom_3857` (for map tiles) |
| `vehicle` | `(collision_index, vehicle_reference)` | FK → collision |
| `casualty` | `(collision_index, casualty_reference, casualty_seq)` | FK → collision; FK `(collision_index, vehicle_reference)` → vehicle. `casualty_seq` = 1 except where a reference was reused (`is_reference_reused`, FU-008) |
| `lookup_code` | `(table_name, field_name, code)` | Labels from the official data guide |
| `lookup_conversion` | — | 2011→2024 code mapping for `*_historic` fields |
| `quarantine` | — | Rejected or altered source rows, with `reason` and the original record as JSON |

**Conventions**

- Coded fields are `smallint` and keep `-1` ("data missing or out of range"), because that value has a label.
- Measures (ages, engine size, coordinates, road numbers) convert `-1` to `NULL`.

## Analysis layer (`mart`)

`mart` is rebuilt with every load and swapped in together with `core`, in the same transaction. It contains only decoded or counted recorded data; nothing is inferred (see FU-001).

| Object | What it's for |
|---|---|
| `collision` (view) | `core.collision` plus `collision_summary`: casualties by severity and road-user group, adjusted severity sums, vehicles by road-user group, `involves_*` flags (pedal cycle, motorcycle, bus, HGV, PPT, …), `has_pedestrian_casualty`, youngest/oldest driver age |
| `collision_decoded`, `vehicle_decoded`, `casualty_decoded` (views) | Every coded field plus a `<field>_label` column; vehicles and casualties also get `road_user_group` |
| `field_catalog` | One row per field: kind, description, first/last year recorded, % populated per year, labelled?, harmonisation note. Use it to drive slicers and "recorded from …" hints |
| `code_counts` | Rows per field × code × year, with labels, for slicer option lists and quick trends |
| `road_user_group` | The mapping from `vehicle_type` / `casualty_type` codes to groups (era-specific codes included) |
| `collision_grid` | Collision counts by severity and year on two grid sizes, for fast zoomed-out map tiles |

**Across years:**
- The 2024-coded fields (`vehicle_manoeuvre`, `junction_detail`, `pedestrian_crossing`, `carriageway_hazards`, …) are back-filled by DfT for all years and are the ones to use for analysis across years.
- The `*_historic` columns keep pre-2024 detail.
- Where DfT left gaps, they stay gaps; `field_catalog` shows them.

```sql
-- e.g. dark, wet collisions involving a motorcycle in 2020-2025, with labels
SELECT collision_index, collision_date, light_conditions_label, road_surface_conditions_label
FROM mart.collision_decoded
WHERE collision_year BETWEEN 2020 AND 2025
  AND light_conditions IN (4, 5, 6, 7)
  AND road_surface_conditions = 2
  AND involves_motorcycle;
```

## Reference data (`geo`)

All of it is open data (OGL; traffic signals from OpenStreetMap under the ODbL), loaded with `stats19 refresh-reference`. The `watch` scheduler re-loads any dataset older than 90 days.

| Table | Source | Rows | Used for |
|---|---|---|---|
| `postcode` | OS Code-Point Open | 1.75 M | Postcode search |
| `place` | OS Open Names (places, roads, schools, hospitals, stations) | 0.97 M | Place and road search |
| `boundary` | ONS Open Geography (latest vintage, found automatically; GB only) | 207 highway authorities, 350 districts, 43 police force areas | Area filters and cluster-site analysis |
| `value_of_prevention` | DfT RAS4001 | 80 | Value of prevention for cluster sites (labelled with price year) |
| `traffic_count_point` | DfT road traffic statistics: count points + Major Road Database (MRDB) link extents | 46,754 (17,941 major links) | Traffic layer and count-point cards; `quality` says how reliable the latest flow is |
| `traffic_aadf` | DfT AADF by count point, year and vehicle type, 2000 onwards | 0.6 M | Flow history and vehicle mix |
| `traffic_la` | DfT local authority traffic (vehicle-miles, all roads) | 6.8 k | Authority traffic trend |
| `road_link`, `road_node`, `motorway_junction` | OS Open Roads (GeoPackage, read without GDAL) | 3.96 M links, 3.35 M nodes (~2.7 GB), 669 numbered motorway junctions | The road network: traffic link geometry and junctions |
| `traffic_link`, `traffic_stretch` | Built from the two above (dataset `traffic_links`) | 41.5 k count points | The OS roads each count applies to: major links cut from OS roads at DfT's junctions, minor-road stretches grown from the count point |
| `osm_node` | OpenStreetMap `highway=traffic_signals` and `highway=mini_roundabout` (Geofabrik GB extract, read with pyosmium; dataset `osm_nodes`) | 97 k (75 k junction signals, 7 k crossing-only, 15 k mini-roundabouts) | Which junctions are signal-controlled, and mini-roundabouts OS doesn't mark |
| `junction`, `junction_arm`, `junction_node` | Built from OS Open Roads + signals + traffic links (dataset `junctions`) | 1.0 M junctions (~1.3 GB with arms and nodes) | Junctions as COBALT sees them: roundabouts, T, crossroads, multi-arm; arms with their DfT counts |
| `junction_collision` | STATS19 junction collisions of the last 10 years → nearest junction within 25 m (dataset `junction_collisions`) | 0.53 M | Collisions and rates per million vehicles entering |
| `safety_unit`, `safety_model` | Safety performance functions (negative binomial, statsmodels) per peer group, and Empirical Bayes for each major link and counted junction, last 5 years (dataset `safety`) | 143 k sites, 20 models | "Compared with similar roads/junctions" and the ranked "worse than similar sites" list |
| `population` | ONS mid-year population estimates, every county and unitary authority, via the Nomis API (`NM_2002_1`), last 20 years | 4.4 k | Casualties per 100,000 people |
| `authority`, `authority_year`, `authority_peer` | Built from population + DfT traffic + boundaries (dataset `authorities`) | 207 authorities, 15 peers each | Area → Rates: vehicle-km (all, major, minor), road length and population per authority and year, and its most similar authorities |
| `collision_link` | Every collision of the last 10 years → best-scoring OS link within 25 m, DfT's feasibility method (dataset `collision_links`) | 1.1 M (99.1% matched) | Collisions and rates per 100 M vehicle-km on each count point's road |

Place names also label cluster sites ("near Sidmouth Road, Exeter"). The road network loads in about 1 minute (`--dataset road_network`, 1 GB download); the traffic tables load in about 15 s. Either load rebuilds the traffic links (~70 s) and the junctions (~2.5 min): `docker compose run --rm pipeline refresh-reference --dataset traffic` (run in the `pipeline` service, which has the download volume). Signals and mini-roundabouts: `--dataset osm_nodes` (2.2 GB download, deleted after the 5 s read). Junction and link matches re-run after every STATS19 load (about 1 min).
