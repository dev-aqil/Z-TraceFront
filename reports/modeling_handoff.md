# Person A model-ready handoff — M8

Person A workflow COMPLETE. CHEMICAL MODEL_READY for the named retrospective detection task only. BIOLOGICAL and COLD_CHAIN remain BLOCKED. No ML model was trained.

## Dataset and target contract

- Dataset/version: `chemical_imidacloprid_detection_training_v1` / 1.0; binary classification.
- File: `data/processed/chemical_imidacloprid_detection_training_v1.csv`; 9,871 rows, 18 columns.
- SHA-256: `686885fa458a9f098df9133058b0e007482d92307ba495eb996436c9c664afde`.
- One row represents One unambiguous original imidacloprid analytical result for one PDP 2024 sample; at most one row per sample.
- Target: `imidacloprid_detected`. Publisher original-extraction imidacloprid detection (O=1) versus validated well-recovered nondetect (ND=0). NP marginal-performing nondetect and R re-extraction excluded. Nondetect is assay-relative, not zero residue or safe food.
- Positive class: 1 = publisher MEAN O (original-extraction imidacloprid detection)
- Exclusions: one re-extraction in this release; any NP or ambiguous repeated sample/analyte group is excluded by policy. All other analytes outside scope.

## Person B input contract

Read `data/processed/chemical_imidacloprid_detection_training_v1.readiness.json` and require `model_ready is true`, verify all pinned hashes, then use `data/processed/chemical_imidacloprid_detection_training_v1.features.json`. `load_model_ready(Path.cwd())` performs these checks and returns (X records, y values, identifier/metadata records).

- Numeric: `pdp_sample_unit_count`, `pdp_collection_dow_iso`, `pdp_collection_doy`, `pdp_collection_isoweek`
- Categorical: `pdp_commodity_code`, `pdp_commodity_type_code`, `pdp_origin_code`, `pdp_import_origin_country_code`, `pdp_product_claim_code`
- IDENTIFIER_ONLY: `observation_id`, `pdp_sample_id`, `pdp_source_row_number`, `pdp_result_source_row_number`
- METADATA_ONLY: `collection_date`, `observation_time`, `source_release`, `analyte_code`
- FORBIDDEN: `result_mean`, `result_concen`, `result_concen_raw`, `result_concen_missing_reason`, `result_annotate`, `result_confmethod`, `result_confmethod2`, `result_quantitate`, `result_extract`, `result_determin`, `result_lod`, `result_lab`, `result_testclass`, `contaminated`, `unsafe_food`, `pesticide_exceedance`, `recall_status`, `previous_positive_rate`, `full_history_count`, `future_weather`, `supplier_id`, `pdp_variety_text`

Only explicit FEATURES may enter the default matrix; unknown names are rejected. Do not train on IDs, timestamps, outcome evidence or remaining columns selected by exclusion. Full classification of every candidate/enriched column is in `reports/m7_validation.json`.

## Feature formulas, availability and missingness

Every feature has a typed source/formula, leakage assessment, availability and missingness contract in the feature manifest. Native product/origin/claim/count fields pass through unchanged; weekday/day-of-year/ISO-week derive only from collection_date. No analytical result contributes to a feature.

CSV null is \N. Empty string is distinct; non-null leading backslashes are escaped. Use the provided typed reader rather than default dataframe NA/type inference. IDs stay strings; missing quantity stays missing; country null can mean domestic non-applicability or unknown origin. Fit any imputation/encoding using training only.

All context has a verified public availability upper bound of 2025-12-23, before the fixed retrospective observation_time of 2025-12-24. This does not prove inputs were publicly available at collection or before assays. No historical feature is delivered.

## Split and evaluation

Whole collection days in chronological order, all rows of each sample together. Dataset has one row per sample. Fit all transforms on training only. Require both classes per partition; stop if unsupported.

Later collection-period holdout probes within-2024 drift without analytical sample overlap. All labels released together: this is retrospective temporal validation, not evidence a model could be trained during 2024. No result availability at earlier training boundaries is claimed.

Use the deterministic boundaries and partition counts in `reports/m7_validation.json` (`split_audit`). Group on `pdp_sample_id`; time column `collection_date`. Report prevalence, class-aware metrics and sampling/assay sensitivity caveats. No geographic/facility transfer claim is supported. Person B owns fitting, tuning, calibration, SHAP and final evaluation.

## Joins and pending tasks

M6 evaluated 14 formal proposals: J01 same-release exact SAMPLE_PK approved; five cross-context joins rejected; eight proposals pending. No recall/weather/OpenDOSM history attached. See `reports/m6_join_audit.md` and JSON for every key, clock, cardinality, ambiguity and scientific decision.

BIOLOGICAL: BLOCKED_PENDING_FSIS. Official raw pathogen samples and dictionary not acquired. FDA inspections remain pending independently and cannot substitute pathogen labels.

COLD_CHAIN: BLOCKED_PENDING_SENSOR_DATA. No legitimate specimen-linked sensor/storage/microbial dataset. Ambient NOAA is not refrigeration telemetry. Concentration regression and regulatory exceedance also remain outside the ready task.

## Frozen provenance and reproducibility

Raw paths, source URLs/retrieval clocks and SHA-256 hashes for all captured sources are in the adjacent `.provenance.json`; only the pinned PDP 2024 archive contributes training rows. M1 source manifest/receipt, M2 cleaning, M4 source schema, M5 features, M6 enrichment and M7 audit are versioned and pinned. The 2024 ZIP includes the reviewed dictionary and code workbook.

With the frozen raw store present, run from the repository root:

```bash
PYTHONPATH=src python -m tracefront_data.clean
PYTHONPATH=src python -m tracefront_data.pdp_sample_context_features
PYTHONPATH=src python -m tracefront_data.modeling_handoff --rebuild-check
PYTHONPATH=src python -m tracefront_data.modeling_handoff --verify-only
PYTHONPATH=src python -m unittest discover -s tests -q
```

The handoff command automatically executes M6, checks M7, then publishes M8. Existing versioned data must match a fresh build or the command refuses overwrite. `--rebuild-check` performs two independent raw-to-M2 cleaning rebuilds, reconstructs M5 from those samples, and regenerates final data with byte comparison. Missing raw inputs stop the workflow; no automatic acquisition/version substitution occurs. Restore exact M1 receipts and maintain offline raw backups.

## IBM Z LinuxONE

Portable UTF-8 CSV/JSON, Python 3.11+ standard library, SQLite for upstream cleaning. No pandas/NumPy/Parquet/native data wheel required. Actual s390x execution is untested; only local x86_64 Python 3.11.17/3.14.7 is verified. Validate target Python/sqlite3 before regeneration. Model-library portability belongs to Person B.

## Existing Person B integration

food-risk-ml/docs/data_contract.md is Salmonella/FSIS-only and is NOT applicable to this chemical dataset.

Separate chemical loader using this readiness/whitelist. Do not rename detection to salmonella_positive or pesticide_exceedance. Do not call existing FSIS training entrypoint on these files.

## Scientific interpretation boundaries

- Retrospective supervised association study of the released 2024 PDP cohort only. Digital context and outcomes were released together; pre-assay public availability and operational prospective validation are unproved.
- Detection depends on analyte/commodity assay sensitivity and sampling program; ND is not zero residue, absence of all pesticides, safe food or legal compliance. No tolerance comparison or regulatory exceedance target.
- One fixed parent analyte (967 Imidacloprid); metabolites and other analytes are excluded. No sample-level any-pesticide label or untested negative manufactured.
- One re-extraction excluded under a prespecified conservative original-result policy; NP would be excluded as marginal-performing nondetect. This selection can affect estimand and missingness.
- Temporal collection-date holdout measures later-2024 cohort association, not a model trainable during 2024: all labels were published after the cohort. No future-year generalization is established.
- No verified lot, farm, supplier or facility grouping; repeated upstream entities may remain. Do not claim new-farm/facility performance or representative population prevalence.
- Imbalanced observed target; use prevalence baseline and class-aware metrics. Person B owns fitting, calibration, explanation and evaluation; no model or accuracy claim produced here.
- Country null mixes domestic non-applicability and unknown origin. Quantity null is unknown, never zero. Native categorical tokens are not harmonized; variety text remains withheld.
- No cross-source or historical features; NOAA ambient weather is not cold-chain telemetry. Pending FSIS, inspections and sensor datasets remain unavailable.
- Actual IBM Z LinuxONE/s390x runtime has not been tested. Portable stdlib CSV/JSON path validated locally on x86_64 only.

## Recommended Person B next prompt

> Begin M9 baseline training only for entries with model_ready=true in reports/modeling_handoff.json. Use chemical_imidacloprid_detection_training_v1.csv, target imidacloprid_detected, and exactly the feature whitelist after readiness/checksum validation. Build a separate chemical task loader; the existing FSIS contract is incompatible. Use the documented whole-day collection-date holdout with sample groups and train-only preprocessing. Treat evaluation as retrospective released-cohort association, not prospective 2024 or unsafe-food/exceedance prediction. Keep biological and cold-chain tasks blocked. Verify IBM Z LinuxONE/s390x model dependencies before training. You own fitting, comparison, tuning, calibration, SHAP and final evaluation.
