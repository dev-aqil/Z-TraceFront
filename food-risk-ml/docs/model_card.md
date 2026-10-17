# Model card: Salmonella sample-positivity model (FSIS raw poultry)

**Model version:** `salmonella-xgboost-20261017T062839Z` (XGBoost, Platt-calibrated)
**Trained:** 2026-10-17, on real FSIS data. Full provenance is in `artifacts/registry/<version>/metadata.json`.
**Status:** first genuine model. It is a prioritisation aid with modest discrimination. It is not a safety verdict.

## Intended use

- **Task:** `biological_pathogen_positive`. Estimate the probability that an FSIS raw poultry laboratory sample, described by information known at collection, **tests positive for Salmonella**.
- **Users:** food-safety analysts deciding where sampling or inspection attention is most useful. A human reviews every decision.
- **Output:** a probability, a risk band, and SHAP contributions.
  - `high`: at or above the operating threshold of 0.061
  - `medium`: from 0.035, the cut-off that catches 95% of positives on validation data
  - `low`: below that

## Out of scope

- **Not a food-safety certification.** A low score does not mean a product, batch or establishment is safe. A high score is not evidence of contamination.
- Not a batch, lot or retail-product prediction. The label is one sample's laboratory result.
- Not for automated enforcement, recalls, or public rating of establishments.
- Not for products, pathogens or countries outside the training data (US FSIS-regulated raw poultry only), including Malaysian supply chains.
- Never combined with chemical-residue or cold-chain/spoilage scores into one probability.

## Training data

- **Source:** USDA FSIS Laboratory Sampling Data, Raw Poultry Sampling, FY2014–FY2026. 13 fiscal-year JSON files from https://www.fsis.usda.gov/news-events/publications/raw-poultry-sampling (page dated 10/14/2026, embedded metadata `creation_date` October 09, 2026), downloaded 2026-10-17. SHA-256 hashes are in `data/raw/fsis_raw_poultry/DOWNLOAD_PROVENANCE.json`.
- **Unit:** one FSIS sample (`form_id`), taken from the primary test table only. The secondary table (serotype, allele code, PFGE/WGS, AMR) exists only for positives and is never loaded.
- **Label:** `salmonella_sp_analysis`, where `Positive` = 1 and `Negative` = 0. `NULL` and cancellation reasons are excluded (200 rows).
- **Size:** 325,121 samples, 324,921 labelled, 1,409 establishments, 34 sampling projects, collected 2013-10-01 to 2026-06-30. Overall positive rate 11.6%.
- **Mapping:** `configs/source_mapping.toml`, quoting the FSIS data dictionary. **Status: draft, pending team review.**

## Features

All of these are known at collection:

| Feature | Source |
|---|---|
| `product_category` | FSIS `project_code` (sampling programme) |
| `meta_cat_sample_source_name`, `meta_cat_product_type`, `meta_cat_establishment_state` | primary table |
| `sample_month` | from `collection_date` |
| `est_prior_samples`, `est_prior_positives`, `est_prior_rate_smoothed`, `est_days_since_prior` | Establishment history: earlier results only, counted if `collection_date + 7 days < sample date`. The 7-day lag is an **assumption**, because FSIS publishes no result date. History is pooled across programmes and smoothed toward the training rate. |

Excluded by design:
- every other result for the same sample (Campylobacter, MPN, CFU, plate counts)
- `not_analyzed`, every `*_canceled` field, and the secondary table
- establishment name and number (identifiers)
- recalls

## Procedure

- **Split:** chronological, with whole days per split.
  - train: 2013-10-01 → 2023-02-21 (227,543 samples)
  - validation: 2023-02-22 → 2024-10-10 (48,671)
  - test: 2024-10-11 → 2026-06-30 (48,707)
- **Models:** prior-rate dummy, logistic regression, random forest and XGBoost, each in a single sklearn `Pipeline` with a `ColumnTransformer`. Class reweighting handles imbalance.
- **Selection:** best validation PR-AUC, which picked XGBoost. The test split was not used for any choice. (Since 2026-10-17 a statistical tie rule applies to every model: a paired-bootstrap tie with the leader goes to XGBoost. XGBoost had the best validation PR-AUC here, so the result is the same.)
- **Calibration:** Platt scaling fit on validation scores. It was applied because out-of-fold validation Brier fell from 0.138 to 0.075. Class reweighting had inflated the raw probabilities.
- **Threshold:** from validation only. The policy is the highest-precision threshold that still catches at least 80% of positives, which gives 0.061 on the calibrated scale.

## Results (real data)

**Test period (Oct 2024 – Jun 2026):** 48,707 samples, 9.8% positive. All models use thresholds chosen on validation data.

| Model | PR-AUC | ROC-AUC | Recall | Precision | Specificity | FNR | Brier |
|---|---|---|---|---|---|---|---|
| Dummy (prior rate) | 0.098 | 0.500 | 1.000 | 0.098 | 0.000 | 0.000 | 0.089 |
| Logistic regression | 0.289 | 0.730 | 0.795 | 0.145 | 0.491 | 0.205 | 0.134 |
| Random forest | 0.292 | 0.736 | 0.829 | 0.141 | 0.453 | 0.171 | 0.119 |
| **XGBoost (selected)** | **0.299** | **0.740** | 0.827 | 0.143 | 0.461 | 0.173 | 0.143 raw |
| **XGBoost + Platt (registered)** | 0.299 | 0.740 | **0.827** | **0.143** | **0.461** | **0.173** | **0.079** |

**Confusion matrix of the registered model on test:**

| | Predicted positive | Predicted negative |
|---|---|---|
| Actually positive | 3,946 (TP) | 826 (FN) |
| Actually negative | 23,671 (FP) | 20,264 (TN) |

What this means:
- **Ranking:** the model ranks samples well above chance. PR-AUC is about 3 times the prevalence, and ROC-AUC is 0.74.
- **The three learned models are close.** The gain comes mostly from programme, product and history information, not from model complexity.
- **Probabilities:** after calibration they are usable. Brier is 0.079, against 0.089 for always predicting the base rate.
- **Cost of 80% recall:** about **57% of test samples get flagged `high`**, at a precision of 14%, against a 9.8% base rate. That is a modest lift. The operating point is a policy choice. Validation trade-offs:

| Target recall | Precision | Share of samples flagged | Lift over base rate |
|---|---|---|---|
| 0.9 | 0.116 | 70% | 1.3× |
| 0.8 (current) | 0.134 | 54% | 1.5× |
| 0.6 | 0.180 | 30% | 2.0× |
| 0.5 | 0.207 | 22% | 2.3× |
| 0.3 | 0.298 | 9% | 3.3× |

The full tables are in `reports/thresholds/`. Plots (`pr_curves_val.png`, `calibration_test.png`, `shap_importance.png`) are regenerated by `train` and git-ignored.

## Explainability

Global mean |SHAP| on a test sample, in log-odds:

| Feature | Mean \|SHAP\| |
|---|---|
| project_code (`product_category`) | 0.81 |
| establishment smoothed prior rate | 0.30 |
| sample source name | 0.22 |
| product type | 0.22 |
| establishment state | 0.14 |
| establishment prior sample count | 0.14 |

These describe **how the model's score responds to inputs that correlate with past positives. They are not causes of contamination.** Per-request explanations are computed on the uncalibrated log-odds. Platt scaling is monotonic, so the direction of each contribution is preserved. Each one-hot category has its own contribution. For example, "not a carcass project" can appear as a contribution for a chicken-parts sample.

## Known limitations and bias

- **Targeted sampling.** FSIS sampling is risk-based. `F_*` projects are **follow-up sampling triggered by earlier results** at the establishment, and they run higher than the matching routine HACCP project: chicken carcasses 12.0% vs 4.7%, chicken parts 15.5% vs 9.8%, comminuted chicken 36.9% vs 27.9% (all years). That information is known before the sample, so it is not same-sample leakage, but the model partly learns FSIS's targeting policy, not only plant performance.
- **Programme drift.** Projects start and stop. Exploratory programmes with very high positive rates, such as `EX_CHCAR_RH1` in 2022 (62%) and the `NRTE_EXP_*` projects of 2013–15, fall in training only. The positive rate fell from about 34% in 2014 to about 10% now. Retrain as programmes change, and watch performance by project.
- **Assumed result delay.** FSIS publishes no result-availability date. If results take longer than 7 days, history features are slightly more informed than they would be in real time.
- **Stale history at inference.** The registry snapshot ends 2026-06-30. Predictions for later dates use history only up to that point.
- **Exposure bias.** Heavily sampled plants have precise history; small or new plants shrink toward the mean.
- **Label quality.** Laboratory methods changed over the period (for example, MPN was discontinued in March 2020), and this is not modelled. 200 unlabelled rows are excluded.
- **Moderate discrimination.** ROC-AUC 0.74. Use the model to rank attention, not to decide outcomes.
- **Validation is optimistic.** It was used for selection, calibration and the threshold. The test-period figures are the honest estimate.
