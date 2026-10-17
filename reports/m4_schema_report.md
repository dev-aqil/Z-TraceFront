# M4 — Source-specific canonical mapping design

**COMPLETE for design and validation of the eligible cohort. NOT MODEL-READY.** No source values, raw/interim data, feature tables, final labels or models were created or changed.

## Scope and evidence

Read M3's generated profiles, scientific findings and validation record before defining this contract. Verified the M3 report/code/input fingerprints, all 30 M2 output checksums, M2 producer fingerprints, exact eligible-source coverage, and all 28 M1 raw-artifact records. Reused the matching M3 full typed census; M4 does not need another row-level EDA scan to declare metadata.

Existing M2/M3 changes in the working tree were preserved. Person B's modeling/application code and reports were untouched. M1–M3 evidence and all source tables remain immutable inputs.

Authoritative reviewed metadata is `configs/source_contracts.json`. Its 106 field entries cover every M2 column without inventing fields. The contract and human-readable dictionaries are source-specific; future farm-to-retail observations remain a separate sparse design in `configs/canonical_schema.json`. Only that draft's status and link to the source-contract registry changed; its proposed table/column definitions were preserved.

## Independent table contracts

| Source / M2 table | Proposed canonical source table | Identity within source snapshot/table | Important boundary |
| --- | --- | --- | --- |
| USDA PDP / samples | pdp_samples | pdp_sample_id | Release-local specimen, not food batch or supplier |
| USDA PDP / results | pdp_analytical_results | pdp_source_row_number | Raw analytical record ordinal; sample/analyte alone is not assumed universally unique |
| openFDA / recalls | food_recall_records | recall_number | Product-specific recall; recall_event_id is grouping, not unique record identity |
| NOAA / daily_observations | ghcn_daily_elements | ghcn_station_id + ghcn_reporting_date + ghcn_element_code | Station/day/element, not batch sensor data |
| OpenDOSM / crops_state | crops_state | dosm_annual_reference_date + dosm_state_or_national_name + dosm_crop_type_code | State/national annual aggregates; overlapping levels |
| OpenDOSM / crops_district_production | crops_district_production | annual reference + state + district + crop type + crop species | Independent 2017 production aggregates |
| OpenDOSM / crops_district_area | crops_district_area | annual reference + state + district + crop type + crop species | Independent 2017 area aggregates, different retained keys/counts |

All identities require source-entry, exact raw-artifact SHA-256 and table/archive-member scope. These are key contracts; **no synthetic key values or namespaced ID columns were generated**. PDP samples/results remain separate. Their shared sample key documents a source relationship, not a join performed in M4. No cross-source join is approved.

## Dictionary contents

For each source column, the JSON and CSV record:

- Proposed canonical name, original source dataset/location/column(s), current M2 column, publisher and source provenance.
- Exact logical datatype; nullable contract and observed null count; physical/source-coded unit and its verification status.
- Description, allowed/source-observed values, source-specific missingness semantics, and M2 transformations already performed.
- Declaration-only M4 operation, intended information role, prediction-time availability, leakage class and rationale.
- Predictor approval (false for every field) and explicit pending semantics where needed.

`string` keeps leading zeros and code vocabularies, `integer` retains integer semantics, `decimal` keeps exact source decimals, `date` preserves calendar precision, and `json` retains nested objects including `{}`. There is no float64 coercion, category decoding, imputation or source-specific adapter execution in M4. Nullable flags mirror M2; primary-key requirements are a separate constraint for accepted rows within the snapshot scope.

Allowed/source-observed values are evidence about this release, not a future-release whitelist. Literal empty strings and blank flag characters are preserved as such, not rendered into fabricated categorical codes. An unexpected future code requires review against its applicable release dictionary.

## Important semantic decisions

### PDP

- `SOURCE_ID → pdp_sample_id_suffix_code`: the annual dictionary defines an A–Z uniqueness suffix, P for proxy site, blank by default. It is not supplier/source establishment identity.
- `LAB → pdp_laboratory_code`: analytical laboratory, not production factory. `SITE → pdp_collection_site_code`: collection-site code, not a verified farm/retailer ID.
- `QUANTITY → pdp_sample_unit_count`: individual units in the sample for selected non-clustered products, not batch mass, transport quantity or shipment size.
- Native commodity, country, compound and method codes remain code strings. PDP country codes are not silently relabeled ISO countries.
- `CONCEN`, `LOD`, `CONUNIT`, `MEAN`, `ANNOTATE` and analytical-method/censoring fields stay analytical evidence. LABEL class means existing outcome evidence; no new final target is defined.
- The reviewed unit dictionary specifies M=ppm, B=ppb, T=ppt. This confirms unit-code meanings only; no numeric unit conversion or tolerance comparison is made. ND and NP retain distinct nondetect-quality definitions; publisher presumptive annotations do not become a new legal-exceedance label.
- Generic examples in annual dictionary prose (such as N for nondetect) do not override the release-reviewed MEAN reference vocabulary ND/NP/O/R.

The official annual PDF and reference-workbook member hashes are recorded in the source-contract evidence. The preinstalled `pdftotext` utility was used for this authoring review only, reading the preserved official PDF. It is not a dependency of the contract validator, renderer or tests; no PDF/native package was installed.

### NOAA

The canonical contract retains the long-form daily element and unit. `ghcn_measurement_value` is deliberately not named transport temperature, product-core temperature or batch rainfall. Source flag characters, raw sentinel integers and M2 observation status remain separate quality evidence. Flags are not converted into contamination labels or generic validity booleans.

The day component is a fixed-width slot position; there is no fabricated publisher DAY column. Reporting date remains a date, and historical release timing, interval boundaries and timezone semantics are pending. Quality/coverage policy is future work.

### openFDA

Firm-name/address fields remain recalling-firm metadata, not farm origin or verified supplier identity. Narrative quantity is text, event ID groups products, and the empty openFDA metadata object is not a populated crosswalk. Snapshot status, reason, classification, action and termination are focal leakage candidates. Historical use requires actual field-version availability; report/initiation dates are not substituted for it.

### OpenDOSM

The three aggregate tables remain independent. Year markers are not publication times. Source category spellings such as `fruits` versus `fruit` remain scoped vocabularies; no common food taxonomy is implied. Missing combinations are not zeros; rejected conflict versions remain quarantined.

Both production fields have `unit.status=PENDING`, `canonical=null`, and the name `dosm_production_value`. The source-declared metric-tonne description remains visible as evidence. Especially for the state flower values identified in M3, crop-specific physical interpretation needs confirmation. No alternative counts/stems unit is assumed. Planted area remains hectares (`ha`) as a metadata alias, without changing values.

## Availability, leakage and missing infrastructure

Every table has `history_availability.status=PENDING` and `available_at=null` in its **metadata contract**, not a generated data column. No prediction cutoff or timestamp is invented. Context/measurement/reference fields remain QUESTIONABLE pending availability and task review. SAFE is restricted to lineage/grouping identifiers, with predictor approval still false. LABEL is analytical evidence, and LEAKAGE identifies retrospective context forbidden before it was available.

The source registry has empty table/global predictor allowlists and disabled mapping execution, label materialization and cross-source joins. It contains no implemented history/temperature/weather features, entity crosswalk, supplier score or final training target. The future batch draft's pathogen/chemical/spoilage fields remain unimplemented proposals.

FSIS remains **official source confirmed, raw file not yet acquired**, with an empty mapping. FDA inspections also have an empty mapping pending a real official file. No official-schema fields were guessed for either source.

## Reproduce and validate

```bash
PYTHONPATH=src python -m tracefront_data.contracts
PYTHONPATH=src python -m tracefront_data.contracts --check-only
PYTHONPATH=src .venv/bin/python -m pytest -q tests
```

The first command validates the static registry against actual pinned M2 schemas and M3 profiles, then writes `reports/m4_data_dictionary.md`, `reports/m4_data_dictionary.csv` and `reports/m4_schema_summary.json`. The second validates without writing. No source data table is opened for transformation or written by either command. Deterministic metadata rendering needs only the versioned registry; full upstream verification also needs the restored M1/M2 artifacts and M3 reports.

Python 3.11+ standard library only; no new runtime/native dependencies or model-training optimization. The reused M2 verification helpers import Python's existing `sqlite3` module, so the target Python build must retain the SQLite support already required by M2; no new native compilation is introduced. LinuxONE/s390x execution remains untested. Final command/test/hash evidence is in `reports/m4_validation.json`.

## Remaining holds and next milestone

M4 design is complete; scientific holds remain explicit: OpenDOSM production units, field-version availability, district conflicts, source-scoped entity meaning and task/target definitions. No new final training labels are authorized by a successful metadata check.

Person B may inspect the contracts and dictionaries to plan interfaces and exclusions. M2 tables have not been renamed to these proposed columns and no training table exists. Any future physical adapter or feature must be implemented and validated in its own authorized milestone.

Recommended next prompt: “Begin M5 only. Read M4 contracts and unresolved holds. First assess which feature families have defensible inputs, documented units, prediction cutoffs and availability evidence. Implement only supported source-specific feature work; keep blocked families explicitly pending. Do not join source families, invent labels, train models or treat a metadata contract as availability proof.”
