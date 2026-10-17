# Modeling feature requirements — what Person B needs from Person A

Status date: 2026-10-17. Owner: Person B. These are **requests, not implementation instructions**. Each feature is tied to a source that actually contains it. Nothing here asks Person A to produce a field the source lacks. The handoff format is in [modeling_m8_handoff_contract.md](modeling_m8_handoff_contract.md).

## Rules for every feature

| Rule | Why |
|---|---|
| Declared `availability: "pre_prediction"`: the value was known before the row's `prediction_time` | The handoff gate rejects any other value |
| Labels sit in separate columns listed under `label_columns`, never under `features` | Gate-enforced |
| Identifiers (`observation_id`, `sample_id`, raw facility IDs) are lineage and grouping columns, not features | Avoids memorising IDs; gate-enforced |
| Features derived from labels (history) must declare `label_derived: true` and a `history_cutoff` | Person A's audit rule: count an event only if `event_time < T` and `available_at < T` |
| Missing values are kept missing, with a per-feature `missing_meaning` | Unknown ≠ zero ≠ not applicable (Person A's M2 semantics) |
| Context sources join a label source only through a verified key at the right grain | No cross-source rows without a defensible join |

## Current joinability: none of the context sources can enrich a current label source

| Label source | openFDA recalls | FDA inspections | NOAA weather | OpenDOSM |
|---|---|---|---|---|
| FSIS (US poultry plants) | ❌ FDA-regulated firms, not USDA plants; no firm↔establishment key | ❌ pending; FEI ≠ FSIS establishment ID | ❌ the one station is in Malaysia | ❌ Malaysian statistics |
| PDP 2024 (US samples) | ❌ no sample↔recall key; firm location ≠ food origin | ❌ pending; collection SITE ≠ facility | ❌ Malaysian station | ❌ Malaysian statistics |

So the **first models will use only within-source features.** Enrichment joins become a request only when a verified key exists. An example is US weather keyed by sampling state and date, which would need a US station set; that is not acquired.

## A. Biological — `pathogen_positive` (FSIS)

| Feature (canonical) | FSIS field | dtype | Required | Availability | Leakage notes |
|---|---|---|---|---|---|
| `prediction_time` | `collection_date` (date boundary) | timestamp | required | — | Collection date, not result date |
| `factory_id` | `establishment_id` | grouping ID | required | — | Grouping and history key, not a feature |
| `sampling_program` | `project_code` | categorical | required | pre-prediction | `F_*` = follow-up sampling after an earlier result. Legitimate, but documented as targeting. |
| `commodity` | `sample_source_name` | categorical | optional | pre-prediction | — |
| `food_type` | `product_type` | categorical | optional | pre-prediction | `NULL` for most projects (inapplicable, not unknown) |
| `state` | `establishment_state` | categorical | optional | pre-prediction | Plant location, not food origin |
| `analyte` + `pathogen_positive` + `label_status` | `salmonella_sp_analysis` | label | required | — | Never a feature |
| Establishment history (`previous_test_count`, `previous_positive_tests`, `days_since_previous_test`) | derived from labels | numeric | Person B computes | before T minus the result lag | FSIS publishes **no result-availability date**, so the lag is an assumption (7 days, agreed). Person B computes history in the pipeline so training and serving match. |

**Not requested from FSIS** (the source lacks them): temperatures, storage/transport, batch or shipment IDs, supplier, processing parameters.

## B. Chemical — `pesticide_detected` / `residue_concentration` (PDP 2024)

| Feature | PDP field | dtype | Required | Availability | Leakage notes |
|---|---|---|---|---|---|
| `prediction_time` | YEAR/MONTH/DAY | date | required | — | Single 2024 release, so temporal evaluation is within-year |
| `analyte` | PESTCODE | grouping | required | — | One model per pesticide or family |
| `commodity` | COMMOD | categorical | required | pre-prediction | — |
| `commodity_type` | COMMTYPE | categorical | optional | pre-prediction | — |
| `claim` | CLAIM | categorical | optional | pre-prediction | e.g. organic claims, as documented |
| `origin`, `country` | ORIGIN, COUNTRY | categorical | optional | pre-prediction | COUNTRY null for domestic/unknown (Person A M2): keep the null with its reason |
| `state` | STATE | categorical | optional | pre-prediction | Sampling state, not growing state |
| `grow_state`, `pack_state`, `dist_state` | GROWST, PACKST, DISTST | categorical | optional | pre-prediction | Heavily missing (8,926 / 7,817 / 2,661 of 9,872); keep the missing reason |
| `distribution_type` | DISTTYPE | categorical | optional | pre-prediction | — |
| `variety` | VARIETY | categorical | optional | pre-prediction | Literal N/A/Na retained by Person A; mapping needed |
| `site` | SITE | grouping ID | required | — | Collection site; grouping, not a feature |
| `lab`, `test_class` | LAB, TESTCLASS | categorical | **questionable** | assignment time | Lab and method determine the detection limit. They help detection prediction, but encode the measurement process, not the food. Use only in a documented ablation. |
| Labels | MEAN, CONCEN, LOD, ANNOTATE, QUANTITATE, CONFMETHOD(2), EXTRACT, DETERMIN | label evidence | — | — | Never features |
| Same-sample other-pesticide results | results table | — | **forbidden by default** | post-analysis | Same-sample lab results |

## C. Cold chain / spoilage (sources not acquired)

Requested only once a source is acquired and its fields are observed. Names follow Person A's `feature_snapshots` table.

| Feature group | Examples | dtype | Availability rule |
|---|---|---|---|
| Storage | `storage_avg_temp_c`, `storage_max_temp_c`, `storage_duration_hours`, `storage_humidity_pct` | numeric | Readings with `observed_at` and `available_at` ≤ T only (prefix windows) |
| Transport | `transport_avg_temp_c`, `transport_max_temp_c`, `transport_duration_hours`, `number_of_stops` | numeric | Completed stops and readings by T only; no final-manifest totals |
| Excursions | `temperature_excursion_count`, `total_minutes_above_threshold`, `maximum_temperature_deviation_c`, `longest_temperature_excursion_min` | numeric | Threshold declared per product (`temperature_policy_id`); prefix only |
| Coverage | `temperature_missing`, `temperature_coverage_fraction` | boolean/numeric | Needed to separate "no excursion" from "no data" |
| Product | `food_type`, `commodity`, `ph`, `moisture_pct` | mixed | Only if measured before T |
| Grouping | `experiment_id`, `batch_id`, `shipment_id` | ID | For grouped splits |
| Labels | `microbial_count` + unit, `spoilage_class`, `storage_condition_class` | label | Measured after T; never features of each other |

## Historical risk features (any domain)

`previous_recalls_365d`, `failed_inspections_365d` and `days_since_previous_incident` are **not requested** until a verified entity crosswalk to the label source exists and historical availability is known. Current recall status and termination fields reveal the future and are never requested.
