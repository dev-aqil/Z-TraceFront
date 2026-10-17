# Model card: Salmonella sample-positivity model (FSIS raw poultry)

> **Status: NOT TRAINED ON REAL DATA.** The FSIS data could not be downloaded from the build environment (HTTP 403 from www.fsis.usda.gov). No real evaluation results exist. Every metric produced so far comes from a synthetic test fixture and is a code check only. Registry metadata and API responses carry `trained_on_synthetic_data: true` for such models. Update this card after the first genuine training run, using `reports/final_model.json` and `reports/metrics.csv`.

## Intended use

- **Task:** `biological_pathogen_positive`. Estimate the probability that an FSIS raw poultry laboratory sample with given pre-sampling characteristics (collection date, product category, establishment history) **tests positive for Salmonella**.
- **Users:** food-safety analysts prioritising sampling and inspection attention, with a human reviewing every decision.
- **Output:** a probability, a risk band (`high`: at or above the validation-chosen operating threshold; `medium`: within the validation 95%-recall net; `low`: below it), and SHAP contributions.

## Out of scope

- **Not a food-safety certification.** A low score does not mean a product, batch or establishment is safe. A high score is not evidence of contamination.
- Not a batch, lot or retail-product safety prediction. The label is a sample's laboratory result.
- Not for automated enforcement, recalls or public ratings of establishments.
- Not for products, pathogens or countries outside the training data (US FSIS-regulated raw poultry only).
- Not combined with chemical-residue or cold-chain/spoilage scores into one probability. Those are separate models.

## Training data (planned)

- **Source:** USDA FSIS Laboratory Sampling Data, Raw Poultry Sampling section: https://www.fsis.usda.gov/science-data/data-sets-visualizations/laboratory-sampling-data
- **Mapping:** source columns and positive/negative codes are mapped in `configs/source_mapping.toml` after inspecting the files and official metadata. Status: **unfilled**.
- **Provenance recorded per model:** SHA-256 hashes of the raw files and the canonical file, the mapping hash, the git commit, and library versions (`metadata.json`).

## Features

- `product_category` and `sample_month` (one-hot; categories with fewer than 10 occurrences are bucketed).
- Establishment history from strictly earlier, already-reported results: prior samples, prior positives, a smoothed prior rate, and days since the prior sample. The label lag is an assumed 7 days.
- Optional declared pre-sampling metadata.
- Excluded by design: same-sample results for any pathogen, serotype, AMR, result/report dates, recalls, and any target-derived field.

## Procedure

- **Split:** chronological 70/15/15 with whole days per split. Grouped-by-establishment fallback if dates are unreliable (§6 of the data contract).
- **Baselines:** prior-rate dummy, logistic regression, random forest and XGBoost, each in a single sklearn `Pipeline` with a `ColumnTransformer`.
- **Imbalance:** class reweighting by default (`balanced` / `scale_pos_weight`). There is no resampling, so no synthetic samples are created. Reweighting distorts probabilities, which is why calibration is assessed next.
- **Selection:** highest validation PR-AUC, excluding the dummy. The test split is never used for any choice.
- **Calibration:** Platt scaling fit on validation scores. It is applied only if 5-fold out-of-fold Brier on validation improves. A reliability diagram on test is saved.
- **Threshold:** from validation only. Default policy: the highest-precision threshold with recall ≥ 0.80. Recall is prioritised because a missed positive costs more in a screening setting. The full precision/recall trade-off table is saved per model.
- **Metrics (val and test):** precision, recall, F1, specificity, false negative rate, PR-AUC, ROC-AUC, Brier score, confusion matrix, prevalence.

Note: the validation set is used for selection, calibration and the threshold. Validation numbers are therefore optimistic. The test numbers are the honest estimate.

## Evaluation results

**None.** No genuine training run has happened. Do not quote numbers from synthetic runs.

## Explainability

SHAP values (TreeExplainer for tree models, LinearExplainer for logistic regression) are computed on the uncalibrated model score, in log-odds or probability units as reported. They describe **how the model's score responds to its inputs, which are correlated with past positives. They do not identify causes of contamination.** Global importance is the mean |SHAP| on a test sample.

## Known limitations and bias

- **Non-random sampling.** FSIS sampling is risk-based and programme-driven. Establishments and products are not sampled uniformly, and follow-up sampling may cluster after failures. The model learns positivity *among sampled units*, which can differ from true prevalence.
- **Exposure bias in history features.** Heavily sampled establishments have more precise history. Small or new establishments shrink toward the mean.
- **Label quality.** Results depend on laboratory method sensitivity and method changes over time, and those changes are not modelled. Codes that are neither positive nor negative are excluded, which may bias results if exclusions are not random.
- **Temporal drift.** Policy, performance standards and plant practices change. Retrain periodically and monitor test-period performance.
- **Assumed label lag.** If real results take longer than 7 days, history features at inference are slightly more informed than they would be in real time. Confirm the turnaround and update `label_lag_days`.
- **Inference history is a snapshot.** Establishment history in the registry ends at the training data's last date.
- **Geography.** US FSIS data only. Using it for Malaysian or other supply chains would be out of distribution.
