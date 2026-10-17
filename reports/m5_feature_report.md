# M5 — Feature feasibility and readiness

**Milestone PARTIAL. Assessment COMPLETE. 2 family(ies) cleared review for implementation; the remaining families stay blocked. NOT MODEL-READY (no joins/labels/training have occurred).**

pdp_collection_calendar, pdp_product_context now have a documented experiment, prediction cutoff and field-specific official availability evidence; their implementation (if any) is produced by a separate materialization module, not this assessor. Every other family still lacks required inputs, units, cutoff definition, availability evidence or predictor review. No cross-source join, final label or model was implemented anywhere in M5.

## Family assessment

| Family | Status | Unresolved requirements |
| --- | --- | --- |
| pdp_product_context | REQUIRES_IMPLEMENTATION_REVIEW |  |
| pdp_collection_calendar | REQUIRES_IMPLEMENTATION_REVIEW |  |
| pdp_input_missingness | BLOCKED | MISSINGNESS_SEMANTICS_POLICY_UNDEFINED, PREDICTION_TIME_AVAILABILITY_UNVERIFIED, PREDICTOR_APPROVAL_PENDING |
| cold_chain_temperature | BLOCKED | BATCH_SENSOR_SERIES_ABSENT, EXPERIMENT_DEFINITION_PENDING, NO_ELIGIBLE_SOURCE_INPUTS, PREDICTION_CUTOFF_UNDEFINED, PREDICTION_TIME_AVAILABILITY_UNVERIFIED, PRODUCT_STAGE_TEMPERATURE_POLICY_ABSENT, SENSOR_QA_GAP_POLICY_UNDEFINED |
| supply_chain_timing | BLOCKED | EXPERIMENT_DEFINITION_PENDING, EXPIRY_SHELF_METADATA_ABSENT, NO_ELIGIBLE_SOURCE_INPUTS, PREDICTION_CUTOFF_UNDEFINED, PREDICTION_TIME_AVAILABILITY_UNVERIFIED, SUPPLY_CHAIN_ENDPOINTS_ABSENT |
| supplier_facility_test_history | BLOCKED | COMPARABLE_TEST_POLICY_UNDEFINED, EXPERIMENT_DEFINITION_PENDING, FOCAL_SAMPLE_EXCLUSION_POLICY_UNDEFINED, PREDICTION_CUTOFF_UNDEFINED, PREDICTION_TIME_AVAILABILITY_UNVERIFIED, TEST_RESULT_AVAILABILITY_ABSENT, VERIFIED_SUPPLIER_FACILITY_ID_ABSENT |
| recall_history | BLOCKED | EXPERIMENT_DEFINITION_PENDING, HISTORICAL_RECALL_FIELD_VERSIONS_ABSENT, HISTORY_WINDOW_POLICY_UNDEFINED, PREDICTION_CUTOFF_UNDEFINED, PREDICTION_TIME_AVAILABILITY_UNVERIFIED, VERIFIED_RECALL_ENTITY_LINKAGE_ABSENT |
| inspection_history | BLOCKED | EXPERIMENT_DEFINITION_PENDING, INSPECTION_FAILURE_POLICY_UNDEFINED, NO_ELIGIBLE_SOURCE_INPUTS, PREDICTION_CUTOFF_UNDEFINED, PREDICTION_TIME_AVAILABILITY_UNVERIFIED, SOURCE_NOT_ACQUIRED, VERIFIED_SUPPLIER_FACILITY_ID_ABSENT |
| weather_environment | BLOCKED | EXPERIMENT_DEFINITION_PENDING, PREDICTION_CUTOFF_UNDEFINED, PREDICTION_TIME_AVAILABILITY_UNVERIFIED, PREDICTOR_APPROVAL_PENDING, WEATHER_DAY_BOUNDARIES_UNVERIFIED, WEATHER_QA_COVERAGE_POLICY_UNDEFINED, WEATHER_WINDOW_POLICY_UNDEFINED |
| agricultural_area_context | BLOCKED | AGRICULTURAL_RELEASE_AVAILABILITY_ABSENT, EXPERIMENT_DEFINITION_PENDING, GEOGRAPHICAL_LEVEL_POLICY_UNDEFINED, PREDICTION_CUTOFF_UNDEFINED, PREDICTION_TIME_AVAILABILITY_UNVERIFIED, PREDICTOR_APPROVAL_PENDING |
| agricultural_production_context | BLOCKED | AGRICULTURAL_RELEASE_AVAILABILITY_ABSENT, EXPERIMENT_DEFINITION_PENDING, GEOGRAPHICAL_LEVEL_POLICY_UNDEFINED, PREDICTION_CUTOFF_UNDEFINED, PREDICTION_TIME_AVAILABILITY_UNVERIFIED, PREDICTOR_APPROVAL_PENDING, UNIT_VERIFICATION_PENDING |

## pdp_product_context

Potential product/category/origin/sample-unit predictors from the sample table, preserving native codes.

Evaluate each referenced source table independently. No joined feature vector is authorized.

| Source table / existing M2 field | Intended use | Units | Field / historical availability |
| --- | --- | --- | --- |
| usda_pdp.samples / commod | INPUT | NOT_APPLICABLE | M5_VERIFIED / M5_VERIFIED |
| usda_pdp.samples / commtype | INPUT | NOT_APPLICABLE | M5_VERIFIED / M5_VERIFIED |
| usda_pdp.samples / origin | INPUT | NOT_APPLICABLE | M5_VERIFIED / M5_VERIFIED |
| usda_pdp.samples / country | INPUT | NOT_APPLICABLE | M5_VERIFIED / M5_VERIFIED |
| usda_pdp.samples / variety | INPUT | NOT_APPLICABLE | M5_VERIFIED / M5_VERIFIED |
| usda_pdp.samples / claim | INPUT | NOT_APPLICABLE | M5_VERIFIED / M5_VERIFIED |
| usda_pdp.samples / quantity | INPUT | CONFIRMED | M5_VERIFIED / M5_VERIFIED |

Unmet source/policy prerequisites:


## pdp_collection_calendar

Assess collection-date context only; existing M2 year/month/day fields are not new M5 features.

Evaluate each referenced source table independently. No joined feature vector is authorized.

| Source table / existing M2 field | Intended use | Units | Field / historical availability |
| --- | --- | --- | --- |
| usda_pdp.samples / collection_date | INPUT | NOT_APPLICABLE | M5_VERIFIED / M5_VERIFIED |

Unmet source/policy prerequisites:


## pdp_input_missingness

Potential missingness indicators only for genuine pre-cutoff sample inputs; no assay-censoring proxy.

Evaluate each referenced source table independently. No joined feature vector is authorized.

| Source table / existing M2 field | Intended use | Units | Field / historical availability |
| --- | --- | --- | --- |
| usda_pdp.samples / country | INPUT | NOT_APPLICABLE | M5_VERIFIED / M5_VERIFIED |
| usda_pdp.samples / quantity | INPUT | CONFIRMED | M5_VERIFIED / M5_VERIFIED |
| usda_pdp.samples / growst | INPUT | NOT_APPLICABLE | PENDING / M5_VERIFIED |
| usda_pdp.samples / packst | INPUT | NOT_APPLICABLE | PENDING / M5_VERIFIED |

Unmet source/policy prerequisites:

- `MISSINGNESS_SEMANTICS_POLICY_UNDEFINED`: Decide unknown/not-applicable/not-measured separately using pre-cutoff evidence; do not encode analytical ND/NP censoring as a predictor.
- `PREDICTION_TIME_AVAILABILITY_UNVERIFIED`: M4 availability remains pending. Sample/reference/report dates and today's retrieval clock do not establish historical as-of values.
- `PREDICTOR_APPROVAL_PENDING`: The referenced base inputs are not on an approved source-specific predictor list.

## cold_chain_temperature

Temperature exposure/statistics/excursions for a real batch-linked product/stage series. NOAA weather is not this series.

Evaluate each referenced source table independently. No joined feature vector is authorized.

| Source table / existing M2 field | Intended use | Units | Field / historical availability |
| --- | --- | --- | --- |
| No defensible acquired source inputs | none | not assessed | pending |

Unmet source/policy prerequisites:

- `BATCH_SENSOR_SERIES_ABSENT`: No acquired eligible table has a genuine batch-linked storage/transport temperature/humidity series with sensor timestamps.
- `EXPERIMENT_DEFINITION_PENDING`: No source-specific deployment experiment has been selected; no new target is defined by this assessment.
- `NO_ELIGIBLE_SOURCE_INPUTS`: Required observations are absent from acquired M4 source tables.
- `PREDICTION_CUTOFF_UNDEFINED`: No documented deployment decision point or precision; do not invent T to unblock features.
- `PREDICTION_TIME_AVAILABILITY_UNVERIFIED`: M4 availability remains pending. Sample/reference/report dates and today's retrieval clock do not establish historical as-of values.
- `PRODUCT_STAGE_TEMPERATURE_POLICY_ABSENT`: No approved product/category/stage thresholds or their effective dates; no universal safe temperature may be substituted.
- `SENSOR_QA_GAP_POLICY_UNDEFINED`: Sensor validation, interpolation, coverage and maximum-gap rules are not defined.

## supply_chain_timing

Elapsed-stage, shelf and expiry durations require real, pre-cutoff endpoints.

Evaluate each referenced source table independently. No joined feature vector is authorized.

| Source table / existing M2 field | Intended use | Units | Field / historical availability |
| --- | --- | --- | --- |
| No defensible acquired source inputs | none | not assessed | pending |

Unmet source/policy prerequisites:

- `EXPERIMENT_DEFINITION_PENDING`: No source-specific deployment experiment has been selected; no new target is defined by this assessment.
- `EXPIRY_SHELF_METADATA_ABSENT`: No verified expiry date, retail arrival or shelf-life record is present.
- `NO_ELIGIBLE_SOURCE_INPUTS`: Required observations are absent from acquired M4 source tables.
- `PREDICTION_CUTOFF_UNDEFINED`: No documented deployment decision point or precision; do not invent T to unblock features.
- `PREDICTION_TIME_AVAILABILITY_UNVERIFIED`: M4 availability remains pending. Sample/reference/report dates and today's retrieval clock do not establish historical as-of values.
- `SUPPLY_CHAIN_ENDPOINTS_ABSENT`: Harvest/processing/dispatch/arrival timestamps and verified batch/shipment identities are absent from the observed tables.

## supplier_facility_test_history

Prior comparable tests for a verified supplier/facility. Sample IDs, collection sites and labs are not those entities.

Evaluate each referenced source table independently. No joined feature vector is authorized.

| Source table / existing M2 field | Intended use | Units | Field / historical availability |
| --- | --- | --- | --- |
| usda_pdp.results / sample_pk | GROUP_KEY | NOT_APPLICABLE | NOT_A_PREDICTOR / PENDING |
| usda_pdp.results / mean | PRIOR_OUTCOME | NOT_APPLICABLE | NOT_A_PREDICTOR / PENDING |

Unmet source/policy prerequisites:

- `COMPARABLE_TEST_POLICY_UNDEFINED`: No approved source/analyte/program/re-extraction comparability and tested denominator policy for history.
- `EXPERIMENT_DEFINITION_PENDING`: No source-specific deployment experiment has been selected; no new target is defined by this assessment.
- `FOCAL_SAMPLE_EXCLUSION_POLICY_UNDEFINED`: History must exclude the focal sample and related duplicate/re-extraction records using explicit identity and timing rules.
- `PREDICTION_CUTOFF_UNDEFINED`: No documented deployment decision point or precision; do not invent T to unblock features.
- `PREDICTION_TIME_AVAILABILITY_UNVERIFIED`: M4 availability remains pending. Sample/reference/report dates and today's retrieval clock do not establish historical as-of values.
- `TEST_RESULT_AVAILABILITY_ABSENT`: Collection dates do not establish when each test result was available; FSIS samples are also not acquired.
- `VERIFIED_SUPPLIER_FACILITY_ID_ABSENT`: M4 explicitly has no supplier/farm/factory crosswalk; PDP SOURCE_ID is a suffix and LAB is an analytical laboratory.

## recall_history

Prior unique available recall events for a verified entity; no current status backfill.

Evaluate each referenced source table independently. No joined feature vector is authorized.

| Source table / existing M2 field | Intended use | Units | Field / historical availability |
| --- | --- | --- | --- |
| openfda_enforcement.recalls / recalling_firm | GROUP_KEY | NOT_APPLICABLE | PENDING / PENDING |
| openfda_enforcement.recalls / event_id | GROUP_KEY | NOT_APPLICABLE | NOT_A_PREDICTOR / PENDING |
| openfda_enforcement.recalls / recall_number | GROUP_KEY | NOT_APPLICABLE | NOT_A_PREDICTOR / PENDING |
| openfda_enforcement.recalls / recall_initiation_date | REFERENCE_TIME | NOT_APPLICABLE | PENDING / PENDING |
| openfda_enforcement.recalls / report_date | REFERENCE_TIME | NOT_APPLICABLE | PENDING / PENDING |

Unmet source/policy prerequisites:

- `EXPERIMENT_DEFINITION_PENDING`: No source-specific deployment experiment has been selected; no new target is defined by this assessment.
- `HISTORICAL_RECALL_FIELD_VERSIONS_ABSENT`: Current snapshot dates and classification/status do not prove historical field versions; original download provenance remains incomplete.
- `HISTORY_WINDOW_POLICY_UNDEFINED`: History event grain, strict event+availability cutoffs and window boundaries remain undefined.
- `PREDICTION_CUTOFF_UNDEFINED`: No documented deployment decision point or precision; do not invent T to unblock features.
- `PREDICTION_TIME_AVAILABILITY_UNVERIFIED`: M4 availability remains pending. Sample/reference/report dates and today's retrieval clock do not establish historical as-of values.
- `VERIFIED_RECALL_ENTITY_LINKAGE_ABSENT`: Recalling-firm text is not a verified supplier/facility entity; no name-based cross-source matching allowed.

## inspection_history

Facility inspection history requires actual official records, identities, availability and classification policy.

Evaluate each referenced source table independently. No joined feature vector is authorized.

| Source table / existing M2 field | Intended use | Units | Field / historical availability |
| --- | --- | --- | --- |
| No defensible acquired source inputs | none | not assessed | pending |

Unmet source/policy prerequisites:

- `EXPERIMENT_DEFINITION_PENDING`: No source-specific deployment experiment has been selected; no new target is defined by this assessment.
- `INSPECTION_FAILURE_POLICY_UNDEFINED`: No approved NAI/VAI/OAI failure interpretation, project-area deduplication and public-availability policy.
- `NO_ELIGIBLE_SOURCE_INPUTS`: Required observations are absent from acquired M4 source tables.
- `PREDICTION_CUTOFF_UNDEFINED`: No documented deployment decision point or precision; do not invent T to unblock features.
- `PREDICTION_TIME_AVAILABILITY_UNVERIFIED`: M4 availability remains pending. Sample/reference/report dates and today's retrieval clock do not establish historical as-of values.
- `SOURCE_NOT_ACQUIRED`: Required official source remains pending, with no invented mapping.
- `VERIFIED_SUPPLIER_FACILITY_ID_ABSENT`: M4 explicitly has no supplier/farm/factory crosswalk; PDP SOURCE_ID is a suffix and LAB is an analytical laboratory.

## weather_environment

Standalone station-window weather summaries; any later location/batch attachment belongs to separately authorized enrichment.

Evaluate each referenced source table independently. No joined feature vector is authorized.

| Source table / existing M2 field | Intended use | Units | Field / historical availability |
| --- | --- | --- | --- |
| noaa_ghcn_daily.daily_observations / station_id | GROUP_KEY | NOT_APPLICABLE | NOT_A_PREDICTOR / PENDING |
| noaa_ghcn_daily.daily_observations / element | GROUP_KEY | NOT_APPLICABLE | PENDING / PENDING |
| noaa_ghcn_daily.daily_observations / observation_date | REFERENCE_TIME | NOT_APPLICABLE | PENDING / PENDING |
| noaa_ghcn_daily.daily_observations / value | INPUT | CONFIRMED_SOURCE_CODED | PENDING / PENDING |
| noaa_ghcn_daily.daily_observations / unit | QUALITY | NOT_APPLICABLE | PENDING / PENDING |
| noaa_ghcn_daily.daily_observations / measurement_flag | QUALITY | NOT_APPLICABLE | PENDING / PENDING |
| noaa_ghcn_daily.daily_observations / quality_flag | QUALITY | NOT_APPLICABLE | PENDING / PENDING |
| noaa_ghcn_daily.daily_observations / source_flag | QUALITY | NOT_APPLICABLE | PENDING / PENDING |
| noaa_ghcn_daily.daily_observations / observation_status | QUALITY | NOT_APPLICABLE | PENDING / PENDING |

Unmet source/policy prerequisites:

- `EXPERIMENT_DEFINITION_PENDING`: No source-specific deployment experiment has been selected; no new target is defined by this assessment.
- `PREDICTION_CUTOFF_UNDEFINED`: No documented deployment decision point or precision; do not invent T to unblock features.
- `PREDICTION_TIME_AVAILABILITY_UNVERIFIED`: M4 availability remains pending. Sample/reference/report dates and today's retrieval clock do not establish historical as-of values.
- `PREDICTOR_APPROVAL_PENDING`: The referenced base inputs are not on an approved source-specific predictor list.
- `WEATHER_DAY_BOUNDARIES_UNVERIFIED`: Daily reporting date is not a proven prediction-time measurement interval/timezone or first-publication time.
- `WEATHER_QA_COVERAGE_POLICY_UNDEFINED`: No approved treatment for QFLAG, MFLAG, source semantics, absent dates or -9999 gaps; missing must not become zero.
- `WEATHER_WINDOW_POLICY_UNDEFINED`: No approved station-window endpoint, period, completed-day rules or heat/rain threshold policy.

## agricultural_area_context

Source-specific area context from independently retained annual tables; no aggregation across geographical levels.

Evaluate each referenced source table independently. No joined feature vector is authorized.

| Source table / existing M2 field | Intended use | Units | Field / historical availability |
| --- | --- | --- | --- |
| opendosm_crops_state.crops_state / planted_area | INPUT | CONFIRMED | PENDING / PENDING |
| opendosm_crops_district_area.crops_district_area / planted_area | INPUT | CONFIRMED | PENDING / PENDING |
| opendosm_crops_state.crops_state / reference_date | REFERENCE_TIME | NOT_APPLICABLE | PENDING / PENDING |
| opendosm_crops_district_area.crops_district_area / reference_date | REFERENCE_TIME | NOT_APPLICABLE | PENDING / PENDING |

Unmet source/policy prerequisites:

- `AGRICULTURAL_RELEASE_AVAILABILITY_ABSENT`: Annual reference years (district 2017; state 2014–2024) are not release dates; no as-of publication/version evidence.
- `EXPERIMENT_DEFINITION_PENDING`: No source-specific deployment experiment has been selected; no new target is defined by this assessment.
- `GEOGRAPHICAL_LEVEL_POLICY_UNDEFINED`: National/state totals overlap; district keys/conflicts and future geographical applicability require explicit policy.
- `PREDICTION_CUTOFF_UNDEFINED`: No documented deployment decision point or precision; do not invent T to unblock features.
- `PREDICTION_TIME_AVAILABILITY_UNVERIFIED`: M4 availability remains pending. Sample/reference/report dates and today's retrieval clock do not establish historical as-of values.
- `PREDICTOR_APPROVAL_PENDING`: The referenced base inputs are not on an approved source-specific predictor list.

## agricultural_production_context

Production context remains pending crop-specific physical-unit confirmation in each source table.

Evaluate each referenced source table independently. No joined feature vector is authorized.

| Source table / existing M2 field | Intended use | Units | Field / historical availability |
| --- | --- | --- | --- |
| opendosm_crops_state.crops_state / production | INPUT | PENDING | PENDING / PENDING |
| opendosm_crops_district_production.crops_district_production / production | INPUT | PENDING | PENDING / PENDING |
| opendosm_crops_state.crops_state / reference_date | REFERENCE_TIME | NOT_APPLICABLE | PENDING / PENDING |
| opendosm_crops_district_production.crops_district_production / reference_date | REFERENCE_TIME | NOT_APPLICABLE | PENDING / PENDING |

Unmet source/policy prerequisites:

- `AGRICULTURAL_RELEASE_AVAILABILITY_ABSENT`: Annual reference years (district 2017; state 2014–2024) are not release dates; no as-of publication/version evidence.
- `EXPERIMENT_DEFINITION_PENDING`: No source-specific deployment experiment has been selected; no new target is defined by this assessment.
- `GEOGRAPHICAL_LEVEL_POLICY_UNDEFINED`: National/state totals overlap; district keys/conflicts and future geographical applicability require explicit policy.
- `PREDICTION_CUTOFF_UNDEFINED`: No documented deployment decision point or precision; do not invent T to unblock features.
- `PREDICTION_TIME_AVAILABILITY_UNVERIFIED`: M4 availability remains pending. Sample/reference/report dates and today's retrieval clock do not establish historical as-of values.
- `PREDICTOR_APPROVAL_PENDING`: The referenced base inputs are not on an approved source-specific predictor list.
- `UNIT_VERIFICATION_PENDING`: No confirmed canonical physical unit; retain publisher declarations without converting.

## Direct focal-input exclusions

20 existing outcome/retrospective fields are excluded as direct focal inputs; these are evidence roles, not new labels.

| Source table | M2 field | Canonical declaration | Role / leakage |
| --- | --- | --- | --- |
| openfda_enforcement.recalls | center_classification_date | recall_classification_date | RETROSPECTIVE_CONTEXT / LEAKAGE |
| openfda_enforcement.recalls | classification | recall_classification | RETROSPECTIVE_CONTEXT / LEAKAGE |
| openfda_enforcement.recalls | distribution_pattern | recall_distribution_text | RETROSPECTIVE_CONTEXT / LEAKAGE |
| openfda_enforcement.recalls | initial_firm_notification | recall_notification_method | RETROSPECTIVE_CONTEXT / LEAKAGE |
| openfda_enforcement.recalls | reason_for_recall | recall_reason_text | RETROSPECTIVE_CONTEXT / LEAKAGE |
| openfda_enforcement.recalls | status | recall_status | RETROSPECTIVE_CONTEXT / LEAKAGE |
| openfda_enforcement.recalls | termination_date | recall_termination_date | RETROSPECTIVE_CONTEXT / LEAKAGE |
| openfda_enforcement.recalls | voluntary_mandated | recall_action_type | RETROSPECTIVE_CONTEXT / LEAKAGE |
| usda_pdp.results | concen | pdp_residue_concentration | OUTCOME_EVIDENCE / LABEL |
| usda_pdp.results | lod | pdp_detection_limit | OUTCOME_EVIDENCE / LABEL |
| usda_pdp.results | conunit | pdp_concentration_unit_code | OUTCOME_EVIDENCE / LABEL |
| usda_pdp.results | confmethod | pdp_primary_confirmation_method_code | OUTCOME_EVIDENCE / LABEL |
| usda_pdp.results | confmethod2 | pdp_secondary_confirmation_method_code | OUTCOME_EVIDENCE / LABEL |
| usda_pdp.results | annotate | pdp_result_annotation_code | OUTCOME_EVIDENCE / LABEL |
| usda_pdp.results | quantitate | pdp_quantitation_method_code | OUTCOME_EVIDENCE / LABEL |
| usda_pdp.results | mean | pdp_result_code | OUTCOME_EVIDENCE / LABEL |
| usda_pdp.results | extract | pdp_extraction_method_code | OUTCOME_EVIDENCE / LABEL |
| usda_pdp.results | determin | pdp_determinative_method_code | OUTCOME_EVIDENCE / LABEL |
| usda_pdp.results | concen_raw | pdp_concentration_raw_token | OUTCOME_EVIDENCE / LABEL |
| usda_pdp.results | concen_missing_reason | pdp_concentration_missing_reason | OUTCOME_EVIDENCE / LABEL |

## Scientific boundaries and next evidence

- PDP product/sample fields may eventually support a chemical experiment. Collection is not digital/result availability, sample unit count is not batch mass, and sample-ID suffix/lab/site codes are not supplier/factory entities. Existing year/month/day fields and M2 missingness reasons were not repackaged as new M5 features.
- Prior outcomes can inform history only after strict event AND result/public-availability filtering, verified identities, a tested denominator/comparability definition and focal-sample exclusion. No history feature or final contamination target was created here.
- NOAA's mm/degC mappings are confirmed within element. That does not resolve day boundaries, QA/coverage policy or the timing of public availability. Weather is not a batch-linked cold-chain sensor. No rainfall/temperature window, threshold or missing-day imputation was computed.
- OpenDOSM area units are hectares, but reference year is not release time. Production units remain pending. District conflicts remain quarantined; overlapping state/national totals were not summed.
- Recall status, classification, reason and termination reflect retrospective snapshots. They cannot be backfilled to report/initiation dates. Firm strings do not establish supplier identity, and current recall objects are not safe/contaminated labels.
- Cold-chain and supply-chain timing require actual batch-linked sensor/stage/expiry records. Product-specific safety thresholds cannot be inferred from regional weather or adopted universally.
- FSIS remains **official source confirmed, raw file not yet acquired**. FDA inspections remain pending. No pending source was acquired or fabricated in M5.

## What was implemented and verified

An evidence-based readiness assessment plus, for the cleared families only, a separate `tracefront_data.pdp_sample_context_features` module that re-checks this same assessment before reading the single pinned `usda_pdp.samples` M2 table (no `usda_pdp.results`, no joins) and writing a source-specific, un-joined, unlabeled feature table under `data/interim/m5_v1/`. See `reports/m5_pdp_sample_context_features_report.md` for exactly what it wrote. This assessor itself still performs no materialization. All M1–M4 inputs are checked against their pinned evidence before assessment.

Reproduce: `PYTHONPATH=src python -m tracefront_data.feature_readiness`. Output is limited to `reports/m5_feature_readiness.json` and `reports/m5_feature_report.md`. Completed assessment exits zero; inspect milestone/status counts to distinguish execution success from feature readiness.

Python 3.11+ standard library only. No dependency or native compilation introduced. Existing M2 verification helpers require the same Python SQLite support already documented. LinuxONE/s390x execution remains untested.

Person B may inspect the assessment, not use it as a model-ready feature matrix. Empty allowlists and pending availability are unchanged except where this report states otherwise. This is not the final M7 leakage audit and no training claim follows from the checks.

## Remaining M5 work

pdp_collection_calendar, pdp_product_context are implemented at the M5 source-specific layer only; cross-source enrichment, leakage audit and any label/target remain future milestones. `pdp_input_missingness` stays pending `MISSINGNESS_SEMANTICS_POLICY_UNDEFINED`. The other eight families are unchanged from the prior assessment and still need their own named experiment, cutoff and evidence.

Continue M5 after prerequisites are resolved; do not advance automatically to enrichment or modeling. A suitable next prompt is: 'Continue M5 for one named experiment. Supply the actual decision cutoff, input-availability evidence and applicable unit/quality policies. Reassess readiness and implement only the source-specific features that pass; keep other families pending. No source joins, invented labels or model training.'
