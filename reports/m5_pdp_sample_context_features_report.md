# M5 — PDP sample-context feature materialization

**NOT MODEL-READY. Source-specific, un-joined, unlabeled M5 feature table only.** The table is not a training design, and this report is not the M7 leakage audit.

Families materialized: **`pdp_collection_calendar`, `pdp_product_context`**. All other M5 families remain blocked and were not touched.

- Experiment: pdp_2024_sample_context_retrospective: Evaluate 2024 PDP sample-record context fields (native commodity/category/origin/variety/claim codes, sample-unit count and collection-calendar date) as retrospective study inputs for the publicly released 2024 cohort. No chemical-outcome, recall or inspection target is defined or created by this experiment; usda_pdp.results analytical fields remain excluded as label evidence under their existing M4 OUTCOME_EVIDENCE/LABEL classification, independent of this cutoff.
- Prediction cutoff: **2025-12-23** (precision: DATE (calendar day; the official posting record states a date only, no time-of-day))
- Availability evidence: USDA Agricultural Marketing Service, official dataset page 'PDP Databases and Annual Summaries' — “2024 Data ZIP File - 10.1MB - Posted on 12/23/2025” (evidence: `reports/m5_evidence/usda_ams_pdp_databases_page.md`, retrieved 2026-10-17T07:37:00+00:00)

## What was read

- Single pinned M2 table: `data/interim/m2_v1/usda_pdp/samples.csv` only (9,872 accepted rows; SHA-256 `0d3d5bca6390f4cec5aed0fb35c953a10f996e56546ad2fe36dc1a6c138b979c` pinned against `reports/m2_cleaning_summary.json` before reading).
- `usda_pdp.results` analytical fields were never read; no other source table was consulted.

## What was written

Directory `data/interim/m5_v1`; 1 table, 10 feature columns (lineage columns excluded from the count).

| Column | Source input | Family | Datatype | Unit / derivation |
| --- | --- | --- | --- | --- |
| `pdp_commodity_code` | usda_pdp.samples / commod | pdp_product_context | string | not_applicable: verbatim native PDP commodity code |
| `pdp_commodity_type_code` | usda_pdp.samples / commtype | pdp_product_context | string | not_applicable: verbatim native PDP commodity-form code |
| `pdp_origin_code` | usda_pdp.samples / origin | pdp_product_context | string | not_applicable: verbatim native PDP origin code |
| `pdp_import_origin_country_code` | usda_pdp.samples / country | pdp_product_context | string | not_applicable: verbatim native PDP import-origin country code; null is not imputed |
| `pdp_variety_text` | usda_pdp.samples / variety | pdp_product_context | string | not_applicable: verbatim publisher free-text variety description |
| `pdp_product_claim_code` | usda_pdp.samples / claim | pdp_product_context | string | not_applicable: verbatim native PDP label-claim code |
| `pdp_sample_unit_count` | usda_pdp.samples / quantity | pdp_product_context | integer | count_individual_sample_units: verbatim nonnegative integer sample-unit count; null is not zero |
| `pdp_collection_dow_iso` | usda_pdp.samples / collection_date | pdp_collection_calendar | integer | iso_weekday_1_monday_7_sunday: ISO weekday (1=Monday..7=Sunday) of the validated collection date |
| `pdp_collection_doy` | usda_pdp.samples / collection_date | pdp_collection_calendar | integer | day_of_year_1_366: day of year (1..366) of the validated collection date |
| `pdp_collection_isoweek` | usda_pdp.samples / collection_date | pdp_collection_calendar | integer | iso_week_number_1_53: ISO week number (1..53) of the validated collection date |

Null passthrough counts follow the pinned M2 missingness (no imputation anywhere):
`{"pdp_import_origin_country_code": 6028, "pdp_sample_unit_count": 2046}`.
Lineage columns retained for traceability but excluded from the feature count: `pdp_source_row_number, pdp_sample_id`.

## Output checksums

| Relative to output directory | Bytes | SHA-256 |
| --- | ---: | --- |
| `pdp_sample_context_features.csv` | 419,329 | `23e7e6db133baf2a9097ff839044c7bcf6df73814749a784ec423800d942b51a`
| `pdp_sample_context_features.schema.json` | 6,255 | `7b9d06e67f829e1eeef7cee62ed58e814029baca837492f5ad4018395631493a`

## Not performed

Explicit under this materialization:

- cross-source joins
- label creation
- missingness-indicator features
- model training
- M6 enrichment
- M7 leakage audit
- M8 modeling handoff
- The `pdp_input_missingness` family stayed blocked (`MISSINGNESS_SEMANTICS_POLICY_UNDEFINED` plus unverified `growst`/`packst` field availability), so no missingness-indicator feature was emitted.
- The M2 year/month/day components were not repackaged as new features; the three calendar features are deterministic derivations of `pdp_collection_date` only.
- Native codes pass through verbatim; no cross-source taxonomy, decoding, entity crosswalk or scoring was applied.

## Reproduce

`PYTHONPATH=src python -m tracefront_data.pdp_sample_context_features` (or add `--verify-only` to re-check existing outputs against the pinned summary). The prerequisite assessment is re-executed first: `PYTHONPATH=src python -m tracefront_data.feature_readiness`. Python standard library only.

Person B may inspect this table as a source-specific M5 provenance feature layer with a documented prediction cutoff; it is not an approved model-ready matrix, and the eventual use of native codes as predictors stays subject to later review.
