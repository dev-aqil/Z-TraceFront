# Data dictionary — M0 draft

This document separates **observed source fields** from **proposed future features**. No source has been cleaned or mapped. No predictor is approved yet: the [draft contract](../configs/canonical_schema.json) has an empty predictor allowlist. M4 will freeze a supported subset after M1–M3.

## FSIS source dictionary status — M1

**Official source confirmed, raw file not yet acquired.** The preserved Data.gov metadata for `usda-fsis-105` identifies the dataset, license and official FSIS resource. It does not expose sample-column names, units, assay result codes, or a sample-level schema/dictionary link. Catalog `@type`, `programCode`, `distribution`, issued/modified dates and publisher fields describe the catalog record; they must not be recast as observation features. FSIS sample field mappings and the matching dictionary remain **pending until an official sample file or applicable official documentation is available**. No field names or assay codes have been inferred. The [manual intake convention](../data/raw/fsis/README.md) and [source-status evidence](m1_fsis_source_status.json) document this state.

## Conventions and availability

Logical types: nullable `string`, `float64`, `int64`, `bool`; timestamps are genuine UTC instants; date-only values remain dates with explicit precision. IDs are namespaced strings and metadata/grouping keys, not default predictors. Country/state/district refer to the documented `location_role`, never inferred farm origin.

Unless a row below specifies otherwise, proposed features have **original dataset = unmapped; original column = unverified; transformation applied = none (design only); prediction-time availability = conditional**. Candidate source families are listed, not asserted mappings. Null means unknown/not measured/not applicable; preserve the source-specific missing reason and do not impute here. Only the contract's `required` metadata fields must be nonnull. Missing required time/identity means retain source rows in interim/quarantine rather than invent a training observation.

**SAFE** = structurally eligible metadata or verified past information, subject to per-row availability; **QUESTIONABLE** = needs source/time/target verification; **LEAKAGE** = outcome information forbidden as same-observation predictors; **LABEL** = separate target/evaluation-only data. SAFE does not authorize ID memorization or an unverified join.

## M1 acquired raw schemas (not canonical feature mappings)

The [M1 source manifest](m1_source_manifest.json) records observed field lists, counts, raw code vocabularies, archive member checksums and dictionary provenance. The PDP column order is reviewed against `PDP DataDictionary 2024.pdf` and the exact 2024 ZIP hash pinned in [the acquisition config](../configs/m1_public_sources.json). No historical source is forced into a batch schema and no cleaned column or ML label is generated in M1.

| Source / original fields | Raw datatype and units | Documented meaning and next-stage caveat |
| --- | --- | --- |
| PDP `PDP24Samples.txt`: `SAMPLE_PK`, `STATE`, `YEAR`, `MONTH`, `DAY`, `SITE`, `COMMOD`, `SOURCE_ID`, `VARIETY`, `ORIGIN`, `COUNTRY`, `DISTTYPE`, `COMMTYPE`, `CLAIM`, `QUANTITY`, `GROWST`, `PACKST`, `DISTST` | Headerless pipe-delimited text; retain strings/leading zeros; dictionary declares integer PK/quantity and text categories | One sample identity record; PK is release-local; YEAR is two digits; SITE is collection site, not farm. Blank, space and free-text values remain distinct. ORIGIN 1=US, 2=import, 3=unknown; COUNTRY is an import-origin code. Collection date is not result/publication time. |
| PDP `PDP24Results.txt`: `SAMPLE_PK`, `COMMOD`, `COMMTYPE`, `LAB`, `PESTCODE`, `TESTCLASS`, `CONCEN`, `LOD`, `CONUNIT`, `CONFMETHOD`, `CONFMETHOD2`, `ANNOTATE`, `QUANTITATE`, `MEAN`, `EXTRACT`, `DETERMIN` | Headerless pipe-delimited text; CONCEN/LOD declared double, raw strings retained; M=ppm, B=ppb, T=ppt; all observed 2024 CONUNIT values are M | One analytical result, multiple per sample. `CONCEN` and `MEAN` are candidate outcomes, **LABEL**, not same-observation predictors. Blank concentration denotes nondetect in annual text; ND and NP are different quality classes. Search-app exports have a different layout/representation. |
| PDP `MEAN`: `ND`, `NP`, `O`, `R` | Raw string code; observed vocabulary retained | ND=validated well-recovered nondetect; NP=marginal-performing-analyte nondetect; O=original-extraction detection; R=re-extraction detection. Do not manufacture tested negatives for absent analytes or merge original/re-extraction results without review. |
| PDP `ANNOTATE`: blank, `Q`, `QV`, `V`, `X` observed | Raw string code; preserve blank | Q=below quantifiable level; QV=BQL with presumptive no-tolerance violation; V=presumptive no-tolerance violation; X=presumptive exceedance. These are result annotations and can leak a derived target. They are not universal safe/unsafe batch labels. |
| PDP reference workbook `Tolerance` | Raw workbook cells; declared `PESTCODE`, `COMMOD`, `EPATOL`, `TOLUNIT`, `NOTE`, `COMMENT` in dictionary | Special tolerance strings include NT/EX/SU; action-level notes and effective-date/residue definitions require review. Do not compare concentration with a naive numeric threshold. No tolerance join has been executed. |
| NOAA `.dly`: ID, YEAR, MONTH, ELEMENT, 31 VALUE/MFLAG/QFLAG/SFLAG groups | Fixed-width strings; temperature tenths °C, PRCP tenths mm; -9999 sentinel | One station-month-element row, not one day. Keep flag positions and calendar padding. QFLAG nonblank requires review. Aggregates and availability-time weather joins are future work. |
| OpenDOSM state CSV: `state`, `date`, `crop_type`, `planted_area`, `production` | UTF-8 CSV; publisher annual reference dates; hectares and metric tonnes | One year/state-or-national/crop-type aggregate. State and national totals overlap; annual 01-01 is not publication time. No contamination outcome. |
| OpenDOSM district CSVs: `date`, `state`, `district`, `crop_type`, `crop_species`, `production` or `planted_area` | UTF-8 CSV; annual dates; metric tonnes or hectares | Separate 2017-only district/crop/species tables with different row counts; no automatic one-to-one correspondence or fill of absent values. No join performed. |

FSIS sample fields and FDA inspection export fields remain **pending actual files**. The saved catalogs, dashboard terminology and API documentation do not establish a locally observed sample/export schema. Existing proposed canonical fields below remain a design, not assertions of acquired features.

## Existing openFDA source fields

Original dataset for every row: local `food-enforcement-0001-of-0001.json`, top-level `results[]`. Each raw value is a string except `openfda` (object). Every column can be absent/null in a future release; currently observed missingness is in [audit JSON](openfda_snapshot_audit.json). No transformation has been applied. Availability is after public release **and field-version availability**, not automatically the initiation date. All are context-only; none establishes a contamination label.

| Proposed contextual canonical name | Original column | Type / unit | Meaning, allowed/null and proposed transformation | Availability / leakage |
| --- | --- | --- | --- | --- |
| recall_number | recall_number | string / ID | Product recall ID; one currently missing; retain raw, never fabricate FDA ID | Metadata; SAFE for trace/grouping, exclude predictor |
| recall_event_id | event_id | string / ID | Groups many recalled products; not row-unique | Metadata; SAFE for grouping |
| recall_report_date | report_date | date / day | Enforcement report date; parse strict YYYYMMDD, preserve date precision | QUESTIONABLE publication proxy; revision history required |
| recall_initiation_date | recall_initiation_date | date / day | Initiation date; pre-2000 flag, no guessed correction | QUESTIONABLE event time, not public availability |
| recall_classification_date | center_classification_date | date / day | Center classification date; nullable | LEAKAGE for an earlier focal decision; historical versions only |
| recall_termination_date | termination_date | date / day | Later closure date; nullable | LEAKAGE for an earlier focal decision |
| recall_classification | classification | string / category | Class I, II, III, Not Yet Classified observed; preserve source vocabulary | LEAKAGE as focal outcome; history requires as-of version |
| recall_status | status | string / category | Terminated, Ongoing, Completed observed | LEAKAGE as focal outcome or backfilled historical status |
| recall_product_type | product_type | string / category | Food observed; not a specific commodity | QUESTIONABLE; constant here, exclude |
| recalling_firm_name | recalling_firm | string / text | Firm name; entity resolution requires evidence | QUESTIONABLE; not supplier/farm ID |
| recalling_firm_address_1 | address_1 | string / address | Firm address; nullable | QUESTIONABLE location/matching metadata |
| recalling_firm_address_2 | address_2 | string / address | Supplementary address; nullable | QUESTIONABLE matching metadata |
| recalling_firm_city | city | string / category | Firm city; not farm origin | QUESTIONABLE location context |
| recalling_firm_state | state | string / category | Source state code/string; nullable; country-aware normalization proposed | QUESTIONABLE location context |
| recalling_firm_postal_code | postal_code | string / code | Preserve leading zeros | QUESTIONABLE location context |
| recalling_firm_country | country | string / category | 32 observed strings; controlled crosswalk proposed | QUESTIONABLE location context |
| recall_distribution_text | distribution_pattern | string / text | Narrative distribution, not enumerated retail locations | LEAKAGE/QUESTIONABLE depending on cutoff; no inferred destinations |
| recall_product_description | product_description | string / text | Product narrative; future reviewed commodity extraction | QUESTIONABLE; inspection for embedded outcomes needed |
| recall_reason_text | reason_for_recall | string / text | Outcome narrative, not independently verified lab evidence | LEAKAGE as focal predictor; reviewed historical hazard extraction only |
| recall_code_info | code_info | string / text | Lot/date narrative; nullable; no guaranteed global batch key | QUESTIONABLE parsing metadata |
| recall_more_code_info | more_code_info | string / text | Additional codes; almost entirely missing | QUESTIONABLE; exclude until useful mapping exists |
| recall_quantity_text | product_quantity | string / mixed text | Mixed quantities/units; nullable; not numeric batch size | QUESTIONABLE; explicit parser/unit contract required |
| recall_notification_method | initial_firm_notification | string / category | Source communication method; nullable | LEAKAGE as focal post-event information |
| recall_action_type | voluntary_mandated | string / category | Voluntary/mandated source terminology; nullable | LEAKAGE as focal enforcement outcome |
| recall_openfda_metadata | openfda | object / none | Empty object in every local row; not a usable ID crosswalk | QUESTIONABLE; exclude |

## Proposed observation identifiers, times and product fields

These are future observation metadata or source-specific measurements, not new facts inferred from recall descriptions. All candidate biological/PDP source mappings require their dictionaries; application mappings below are explicitly only for future operational data.

| Canonical field(s) | Type / unit | Meaning, allowed values and intended derivation | Availability / leakage |
| --- | --- | --- | --- |
| observation_id | string / ID | Stable source+record+analyte+prediction-cutoff identifier; required | Metadata; SAFE |
| dataset_id, dataset_version, source_record_id | string / ID | Required provenance; source ID uniqueness defined per release | Metadata; SAFE |
| sample_id, experiment_id | string / ID | Actual specimen/run grouping; null if absent, never inferred from adjacent rows | Metadata; SAFE grouping only |
| batch_id, supplier_id, farm_id, factory_id, shipment_id, retailer_id | string / ID | Real lineage identities, namespaced; no cross-source name matching. Application batch_id/shipment_id can later map from `Batch.batch_id` / `Shipment.shipment_id` | Metadata; QUESTIONABLE crosswalk; exclude raw IDs by default |
| analyte, sampling_program | string / category | Organism/chemical and surveillance program; controlled release-specific mapping | QUESTIONABLE; selection/design variables may be known, outcome-derived subtyping is excluded |
| is_synthetic | bool / flag | Required provenance; synthetic observations isolated from real evaluation | Metadata; SAFE |
| prediction_time | timestamp UTC / instant | Required deployment decision cutoff, chosen before feature extraction | Metadata; SAFE |
| prediction_time_precision | string / category | Required `instant` or `date_boundary`; date-only source uses conservative boundary | Metadata; SAFE |
| sample_time | timestamp UTC or date | Collection time, not report availability; source precision retained | Metadata; QUESTIONABLE if unknown at chosen cutoff |
| food_type, food_category, commodity | string / category | Versioned food taxonomy; source-specific known product identity | QUESTIONABLE until verified; no outcome-text-derived food hints |
| processing_type | string / category | Documented process, e.g. raw/cooked; no assumed defaults | QUESTIONABLE until verified |
| batch_size, batch_size_unit | float64 + string / explicit unit | Nonnegative physical quantity with unit; never parse mixed product_quantity implicitly | QUESTIONABLE until verified |
| moisture_pct | float64 / % | 0–100 or null; percent basis/method retained | QUESTIONABLE if lab measurement returns after cutoff |
| ph | float64 / pH | 0–14 expected under chosen measurement policy; out-of-range flags require review | QUESTIONABLE if unavailable before cutoff |
| shelf_life_days | float64 / days | Nonnegative declared shelf life known at cutoff, not realized time to failure | QUESTIONABLE until source verified |
| country, state, district | string / category | Explicit observation location; country-aware geographic codes | QUESTIONABLE spatial role and historical boundary mapping |
| latitude, longitude | float64 / degrees | WGS84, [-90,90] / [-180,180], or null | QUESTIONABLE until location source verified |
| location_role | string / category | farm, factory, storage, transport, retail, sample_location, or firm_address | Metadata; SAFE; never conflate firm address with farm |
| harvest_time, processing_time, shipment_start, shipment_end, retail_arrival, expiry_time | timestamp UTC or date | Actual documented stage/expiry dates; stage endpoints after T excluded from features. `Shipment.departed_at` is only a candidate operational shipment_start mapping | QUESTIONABLE; future actual end times are LEAKAGE |
| ambient_temperature_c | float64 / °C | Environmental reading, plausible bounds depend on instrument; Fahrenheit → (F−32)×5/9 if declared | QUESTIONABLE; ambient is not product core temperature |
| humidity_pct | float64 / %RH | 0–100; fractional units multiplied by 100 only if documented | QUESTIONABLE until time/unit verified |
| rainfall_mm | float64 / mm per declared interval | Nonnegative; missing observations are not zero rainfall | QUESTIONABLE; completed available interval required |
| process_temperature_c, process_duration_min | float64 / °C, minutes | Declared processing measurements; duration nonnegative, hours×60 only with original unit | QUESTIONABLE if process still ongoing or logs delayed |
| sanitation_score, sanitation_score_scale | float64 + string / documented scale | No universal 0–100 assumption; scale and effective/publication time required | QUESTIONABLE; later inspection score is LEAKAGE |
| packaging_condition | string / category | Documented intact/damaged/other controlled source vocabulary | QUESTIONABLE; must be assessed by cutoff |

## Proposed sensor and historical event tables

| Canonical fields | Type / unit | Meaning / nullable and transformation contract | Availability / leakage |
| --- | --- | --- | --- |
| sensor_reading_id, sensor_id | string / ID | Unique reading key and actual sensor identity; required in sensor table | Metadata; SAFE |
| observed_at, available_at | timestamp UTC / instant | Measurement/event occurrence versus first availability to predictor; both required for eligible sensor rows | Metadata; SAFE after validation; no fabricated availability |
| stage | string / category | farm, factory, storage, transport, retail; source stage required for stage-specific features | QUESTIONABLE until linkage verified |
| temperature_c | float64 / °C | Sensor reading; application `SensorReading.temperature` candidate mapping, unit must be confirmed | QUESTIONABLE until timestamp/unit/quality verified |
| co2_ppm, light_lux | float64 / ppm, lux | Nonnegative, device-aware limits; fruit `CO2` / `Light` are publisher candidate columns only | QUESTIONABLE; condition features, not pathogen evidence |
| quality_flag | string / category | Device/source flag and invalidity reason; retain raw reading separately | Metadata; SAFE for quality review |
| history_record_id, event_id, event_type | string / ID/category | Unique source-version row versus shared event; type test/recall/inspection | Metadata; SAFE; prevent product/event double counting |
| entity_id, entity_namespace, crosswalk_version | string / ID/version | Verified source-scoped entity and versioned crosswalk; nullable means no entity-level join | Metadata; QUESTIONABLE if linkage unverified |
| event_time, available_at, time_precision | instant/date + string | Occurrence, public/operational availability and precision; unknown availability blocks historical feature use | Metadata; QUESTIONABLE until verified |
| source_version, source_retrieved_at | string + UTC instant | Dataset snapshot identity and actual acquisition instant; acquisition is not historical publication time | Metadata; SAFE provenance, not predictors |
| outcome | string / source category | Test/recall/inspection outcome, versioned; not universal positive/negative | LEAKAGE as focal input; prior available outcomes only |

## Proposed derived feature candidates (M5–M6, not implemented)

For every row: original dataset = verified linked sensor/history/weather source **not yet selected**, original column = derived, transformation applied = none yet. Values must be computed only from data eligible at `prediction_time`; until tests and mappings exist all are QUESTIONABLE. Nonnegative quantities allow null unless otherwise noted. Proposed numeric/categorical names do not imply availability in FSIS/PDP.

| Canonical feature(s) | Type / unit | Proposed transformation / allowed values | Prediction availability and leakage condition |
| --- | --- | --- | --- |
| feature_definition_version, temperature_policy_id | string / version | Feature definitions and product/category/stage policy with effective dates | Required provenance for computed values; not predictors |
| storage_avg_temp_c, storage_max_temp_c, storage_min_temp_c | float64 / °C | Pre-cutoff storage sensor window; mean should be time-weighted for irregular sampling | Only eligible prefix window; final-window aggregate leaks |
| storage_duration_hours, storage_humidity_pct | float64 / hours, %RH | Known elapsed storage duration and eligible humidity aggregate (0–100) | No future storage endpoints |
| transport_avg_temp_c, transport_max_temp_c, transport_duration_hours | float64 / °C, hours | Same principle for transport prefix, time-weighted mean | No completed-trip values during an active trip |
| number_of_stops | int64 / count | Observed completed stops by T; no final manifest total as actual stops | Conditional on event availability |
| temperature_excursion_count | int64 / count | Contiguous policy-exceeding episodes, **not reading count** | Product-specific upper/lower policy, gap treatment needed |
| total_minutes_above_threshold | float64 / minutes | Time-integral above configured upper bound; distinguish lower-limit failures separately | Specify interpolation, final interval and max sensor gap |
| maximum_temperature_deviation_c, average_temperature_deviation_c | float64 / °C | Nonnegative departure from policy band; mean time-weighted over covered interval | No universal safe temperature; policy needed |
| temperature_std_c, temperature_range_c | float64 / °C | Document ddof and sampling weighting; range=max−min | Only pre-cutoff readings; null if insufficient coverage |
| longest_temperature_excursion_min | float64 / minutes | Maximum duration of contiguous out-of-policy interval | Gaps cannot automatically be treated as exposure |
| cold_chain_failure_flag | bool / flag | Defined by documented policy and coverage; null if unknown | A proxy outcome when used as target; cannot also predict that same derived target |
| temperature_missing | bool / flag | True when no valid eligible temperature observations | Not a substitute for exposure measurements |
| temperature_coverage_fraction | float64 / fraction | Covered eligible minutes / intended window, [0,1] | Explicit gap policy; no false completeness |
| farm_to_factory_hours | float64 / hours | Processing start − harvest/dispatch reference (definition to freeze) | Both real endpoints known by T, nonnegative |
| processing_to_shipping_hours | float64 / hours | Shipment start − chosen process completion time | Process completion semantics must be confirmed |
| shipping_duration_hours | float64 / hours | Known shipment_end−start for ended trips, otherwise T−start for prefix feature | Do not mix prefix/final semantics without stage metadata |
| total_supply_chain_duration_hours | float64 / hours | T−documented chain origin, not unknown final arrival−origin | Unknown origin stays null |
| days_until_expiry | float64 / days | expiry_time−T; may be negative for expired stock | Declared expiry known at prediction time |
| days_on_retail_shelf | float64 / days | T−retail_arrival; null before arrival | Nonnegative for retail observations |
| previous_positive_tests, previous_test_count, previous_positive_rate | int64, int64, float64 / count, count, fraction | Comparable same-entity/analyte/program tests with event and result availability strictly before T; rate ∈[0,1], null when denominator=0 | Exclude focal specimen and duplicate assays; entity/window must be explicit |
| previous_recalls_365d, previous_recalls_3y | int64 / events | Unique prior available recall events; 365-day and three-calendar-year window definitions to freeze | Not products-per-event; no future status backfill |
| failed_inspections_365d | int64 / inspections | Unique prior available inspections satisfying frozen failure policy (e.g. OAI); VAI not silently treated identically | Need crosswalk, public availability and project-area deduplication |
| days_since_previous_incident, days_since_last_inspection | float64 / days | T minus latest eligible event; null if none observed | Strict event+availability cutoff; no history ≠ no real-world incident |
| rainfall_1d, rainfall_7d, rainfall_30d | float64 / mm | Sum completed eligible station days with reported coverage | Missing days not zero; no partial current-day total |
| avg_temperature_7d, max_temperature_7d | float64 / °C | Mean of defined daily mean series / max of daily max series | Completed available days only; station/distance retained |
| extreme_heat_flag, heavy_rain_flag | bool / flag | Configurable contextual thresholds, not contamination labels | Null without enough coverage/policy; no universal heat/rain threshold |

Canonical durations use `_hours`, not `_hr`, to avoid duplicate aliases. Scope/entity/window are mandatory in feature-definition metadata; separate supplier versus factory feature names must be introduced when actual source data supports both, rather than treating one generic history as both.

## Label table — never included in predictor allowlists

| Canonical name(s) | Type / unit / allowed values | Original source / transformations and meaning | Availability / leakage |
| --- | --- | --- | --- |
| label_id, observation_id, label_source_record_id, label_definition_version | string / ID/version | Determination identity, observation foreign key and evidence provenance; no mappings implemented | Metadata only; exclude from predictors |
| target_name, label_status | string / category | Selected target; status observed/untested/indeterminate/missing. No label inferred from absence of recall | LABEL metadata |
| sample_time, result_available_at, assay_method, analyte | time/date + string | Source specimen, result availability and documented test definition. Sample time can precede delayed label; availability cannot be assumed | LABEL metadata; audit split-time availability |
| pathogen_positive | bool / true,false,null | FSIS assay positive/negative only after validating result codes; unknown/untested remains null | LABEL |
| chemical_exceedance | bool / true,false,null | PDP result compared to matched applicable limit under documented censoring/units; not detection alone. `pesticide_exceedance` is an unsupported alias, not a second target | LABEL |
| microbial_count, microbial_count_unit, microbial_count_scale | float64 + string / CFU per declared mass or volume; raw or log10 | Milk/paneer/beef assays; retain method/unit/scale; never equate CFU/g, CFU/ml and log10 counts | LABEL; LEAKAGE if used to predict a class derived from same count |
| spoilage_class | string / source-specific category | Laboratory/experiment-defined quality class; original beef `Class` candidate mapping, not verified | LABEL; class thresholds/run identities need verification |
| storage_condition_class | string / Good,Bad,null | Fruit `Class` publisher candidate mapping; environmental suitability, not lab spoilage | LABEL proxy; do not rename to pathogen_positive |
| residue_concentration, concentration_unit, detection_qualifier, lod, loq, applicable_limit, limit_reference_id | float64 + strings / explicit original and normalized concentration units | Same-sample analytical evidence and tolerance provenance; concentration/LOD/LOQ units and residue definition must align | LABEL/evidence; exclude from predictors of the same chemical endpoint |

`contamination_label` is deliberately absent: a universal biological/chemical/spoilage label has no defensible definition in M0. Numeric target zero is a valid observed count/negative, not missingness. Result evidence is retained even when a row is ineligible for training.
