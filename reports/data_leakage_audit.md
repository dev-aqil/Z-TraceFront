# Final Person A leakage audit — M7

COMPLETE for the named retrospective chemical detection task. Biological and cold-chain domains remain blocked.

**One row:** One unambiguous original imidacloprid analytical result for one PDP 2024 sample; at most one row per sample.

**Target:** Publisher original-extraction imidacloprid detection (O=1) versus validated well-recovered nondetect (ND=0). NP marginal-performing nondetect and R re-extraction excluded. Nondetect is assay-relative, not zero residue or safe food.

## Explicit column classification

| Column | Classification |
| --- | --- |
| observation_id | IDENTIFIER_ONLY |
| pdp_sample_id | IDENTIFIER_ONLY |
| pdp_source_row_number | IDENTIFIER_ONLY |
| pdp_result_source_row_number | IDENTIFIER_ONLY |
| collection_date | METADATA_ONLY |
| observation_time | METADATA_ONLY |
| source_release | METADATA_ONLY |
| analyte_code | METADATA_ONLY |
| pdp_commodity_code | SAFE_FEATURE |
| pdp_commodity_type_code | SAFE_FEATURE |
| pdp_origin_code | SAFE_FEATURE |
| pdp_import_origin_country_code | SAFE_FEATURE |
| pdp_product_claim_code | SAFE_FEATURE |
| pdp_sample_unit_count | SAFE_FEATURE |
| pdp_collection_dow_iso | SAFE_FEATURE |
| pdp_collection_doy | SAFE_FEATURE |
| pdp_collection_isoweek | SAFE_FEATURE |
| imidacloprid_detected | TARGET |
| result_source_row_number | IDENTIFIER_ONLY |
| result_sample_pk | IDENTIFIER_ONLY |
| result_commod | METADATA_ONLY |
| result_commtype | METADATA_ONLY |
| result_lab | QUESTIONABLE |
| result_pestcode | METADATA_ONLY |
| result_testclass | QUESTIONABLE |
| result_concen | LEAKAGE |
| result_lod | QUESTIONABLE |
| result_conunit | QUESTIONABLE |
| result_confmethod | LEAKAGE |
| result_confmethod2 | LEAKAGE |
| result_annotate | LEAKAGE |
| result_quantitate | LEAKAGE |
| result_mean | LEAKAGE |
| result_extract | QUESTIONABLE |
| result_determin | QUESTIONABLE |
| result_concen_raw | LEAKAGE |
| result_concen_missing_reason | LEAKAGE |
| result_duplicate_of_source_row | METADATA_ONLY |
| pdp_variety_text | QUESTIONABLE |

## Exclusions and duplication

{
  "input_rows": 9872,
  "candidate_rows": 9871,
  "excluded_rows": 1,
  "exclusion_reasons": {
    "excluded_mean_R": 1
  },
  "excluded_records": [
    {
      "pdp_sample_id": "2522",
      "pdp_result_source_row_number": 653881,
      "reason": "excluded_mean_R"
    }
  ],
  "repeated_sample_groups_before_exclusion": 0
}

All ambiguous sample/analyte groups would be excluded in full; no arbitrary first-row resolution. Split unit is the source sample, not an assay panel row. Sample IDs and lineage are never features. Unknown lots/farms cannot be protected by fabricated groups.

## Temporal proof and split

All context available by 2025-12-23 < observation_time 2025-12-24; no historical aggregates.

Whole collection days in chronological order, all rows of each sample together. Dataset has one row per sample. Fit all transforms on training only. Require both classes per partition; stop if unsupported.

Later collection-period holdout probes within-2024 drift without analytical sample overlap. All labels released together: this is retrospective temporal validation, not evidence a model could be trained during 2024. No result availability at earlier training boundaries is claimed.

{
  "method": "TEMPORAL_COLLECTION_PERIOD_RETROSPECTIVE",
  "no_sample_overlap": true,
  "partitions": {
    "train": {
      "rows": 6913,
      "min_date": "2024-01-02",
      "max_date": "2024-09-09",
      "target_counts": {
        "0": 6622,
        "1": 291
      }
    },
    "validation": {
      "rows": 1540,
      "min_date": "2024-09-10",
      "max_date": "2024-11-05",
      "target_counts": {
        "0": 1487,
        "1": 53
      }
    },
    "test": {
      "rows": 1418,
      "min_date": "2024-11-06",
      "max_date": "2024-12-23",
      "target_counts": {
        "0": 1372,
        "1": 46
      }
    }
  },
  "limitation": "Released cohort study only; not a prospective 2024 backtest. No label-availability assumption at earlier collection boundaries."
}

No future recall, inspection, full-history aggregate, weather window, label-derived category, assay result or ID is admitted by the default feature whitelist.

## Scientific limits

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

Full row counts, categorical domains, missingness, numeric ranges, provenance pins and all candidate classifications: `m7_validation.json`.
