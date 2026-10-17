# Model card: Campylobacter sample-positivity model (FSIS raw poultry)

**Model version:** `campylobacter-xgboost-20261017T130600Z` (XGBoost, Platt-calibrated)
**Trained:** 2026-10-17 on real FSIS data. Provenance: `artifacts/registry_campylobacter/<version>/metadata.json`.
**Status:** a prioritisation aid with modest discrimination, not a safety verdict. It is a separate model from Salmonella (`docs/model_card.md`), and its probability is never combined with Salmonella, chemical or cold-chain scores.

## Intended use

- **Task:** `biological_pathogen_positive`. Estimate the probability that an FSIS raw poultry sample, described by information known at collection, **tests positive for Campylobacter by the enrichment method**.
- **Users:** food-safety analysts deciding where sampling or inspection attention helps most. A human reviews every decision.
- **Output:** probability, risk band and SHAP contributions.
  - `high`: score ≥ 0.173 (validation 80%-recall threshold)
  - `medium`: from 0.080 (validation 95%-recall net)
  - `low`: below that. Low does not mean safe.

The out-of-scope list is the same as for the Salmonella card: not a certification, not a batch/lot verdict, not for enforcement or public ratings, not for other products or countries.

## Training data

- **Source:** the same 13 FSIS Raw Poultry Sampling files as the Salmonella model (FY2014–FY2026, SHA-256 hashes in `data/raw/fsis_raw_poultry/DOWNLOAD_PROVENANCE.json`).
- **Label:** `campylobacter_analysis_30ml` (enrichment). `Positive` = 1, `Negative` = 0 (one `NEGATIVE` matched case-insensitively). NULL (133,990 rows: not selected for Campylobacter analysis, or cancelled) is excluded.
- **Direct-plate result excluded:** `campylobacter_analysis_1ml` (~80k samples, ~4% positive) has different sensitivity. Mixing methods would turn a method change into fake drift, so rows tested only by direct plate get no label. Mapping: `configs/source_mapping_campylobacter.toml` (**draft, pending team review**).
- **Size:** 191,131 labelled samples, 1,300 establishments, 23 projects, 2014-08-18 to 2026-06-30, 17.1% positive. Volume is small before FY2019 (under 4k/yr), about 29k/yr for FY2019–FY2023, then about 14k/yr from FY2024.
- **Rates by project (all years):**

| Project | Positive rate |
|---|---|
| Chicken carcasses (`HC_CH_CARC01`) | 22.6% |
| Chicken parts (`HC_CPT_LBW01`) | 18.2% |
| Comminuted chicken | 7.8% |
| Comminuted turkey | 2.2% |
| Turkey carcasses | 1.4% |

## Features

The features are the same as the Salmonella model's: project code, sample source, product type, establishment state, sample month, and establishment history. Establishment history comes from **earlier Campylobacter results only**, counted if `collection_date + 7 days < sample date`. It is an assumed lag, pooled across projects, smoothed toward the training rate with 20 pseudo-samples.

Excluded:
- every other result for the same sample (Salmonella, Campylobacter direct plate, MPN/CFU)
- `*_canceled` fields
- the secondary table
- establishment name and number

## Procedure

- **Split:** fixed calendar dates, shared with every pathogen (`configs/config.toml` `[split] val_start` and `[backtest] sealed_test_start`).
  - train 2014-08-18 → 2023-02-21 (132,842)
  - validation 2023-02-22 → 2024-10-10 (32,490)
  - test 2024-10-11 → 2026-06-30 (25,799)
- **Models:** prior-rate dummy, logistic regression, random forest, XGBoost, each in a single sklearn `Pipeline` with class reweighting.
- **Selection:** best validation PR-AUC, with a tie rule: models within 0.005 of the best are tied, and the tie goes to XGBoost, then LR, then RF.
  - Here RF (0.4359) and XGBoost (0.4354) tied, and XGBoost was chosen.
  - The rule was written **after** seeing this validation result, so it is disclosed here. Its reasons don't depend on the result:
    - The 0.0005 gap is well inside fold-to-fold spread, and the backtest ranked them the other way (0.4024 RF vs 0.4025 XGB).
    - TreeSHAP on the 400-tree forest took more than 15 minutes in training. That would make per-request explanations far too slow for real-time use and the artifact large on LinuxONE.
  - The test split was not used for any choice.
- **Calibration:** Platt on validation scores, applied because out-of-fold validation Brier fell from 0.203 to 0.134.
- **Threshold:** from validation only, the highest-precision threshold with recall ≥ 0.80.

## Rolling backtest (development data only, before the sealed test)

There are four folds, one per fiscal year FY2021–FY2024. Each trains on everything before its start.

| Model | PR-AUC mean (min) | ROC-AUC mean | Recall at 20% budget, mean |
|---|---|---|---|
| Dummy (prior rate) | 0.170 | 0.500 | 0.20 |
| Logistic regression | 0.399 (0.377) | 0.757 | 0.454 |
| Random forest | 0.402 (0.372) | 0.760 | 0.458 |
| XGBoost | 0.403 (0.375) | 0.760 | 0.456 |

Per-fold results are in `reports/campylobacter/backtest/`. The ranking is stable across years even though positivity rose from about 15% to about 19% in FY2023.

## Results on the test period (Oct 2024 – Jun 2026)

25,799 samples, 19.8% positive. Thresholds were chosen on validation.

| Model | PR-AUC | ROC-AUC | Recall | Precision | Specificity | Brier |
|---|---|---|---|---|---|---|
| Dummy (prior rate) | 0.198 | 0.500 | 1.000 | 0.198 | 0.000 | 0.160 |
| Logistic regression | 0.402 | 0.745 | 0.758 | 0.315 | 0.593 | 0.187 (raw) |
| Random forest | 0.426 | 0.746 | 0.786 | 0.305 | 0.556 | 0.173 (raw) |
| **XGBoost + Platt (registered)** | **0.434** | **0.752** | **0.768** | **0.314** | **0.585** | **0.137** |

Confusion matrix of the registered model:

| | Predicted positive | Predicted negative |
|---|---|---|
| Actually positive | 3,927 (TP) | 1,184 (FN) |
| Actually negative | 8,591 (FP) | 12,097 (TN) |

What this means:
- **Ranking:** PR-AUC is about 2.2× prevalence, and ROC-AUC is 0.75. That is similar in strength to the Salmonella model.
- **Probabilities:** calibrated Brier is 0.137, against 0.160 for the base rate.
- **Cost:** 49% of test samples are flagged `high`, catching 77% of positives (validation target 80%), at 31% precision against a 19.8% base rate, a 1.6× lift.
- **Top driver:** the establishment's own Campylobacter history (mean |SHAP| 0.78 log-odds), well ahead of project code (0.26), product type (0.26) and sample source (0.22). For Salmonella, project code dominates. These are associations with past positives, **not causes**.

## Known limitations

- **The test period has been looked at twice.** The first training run on 2026-10-17 used a row-fraction split, so its test window began on 2024-07-30 and overlapped validation and backtest data. Its test PR-AUC (0.437) was seen. That run was discarded because of the misaligned split, not because of its score, and the split was fixed to calendar dates. The final sealed scoring at the end of the project is the last use of this period.
- **Product type labels are inconsistent** across years (`Breast` vs `a. Breast`, `Half-Carcass` vs `Half-carcass`). Each spelling is currently a separate category. Normalising them is planned (feature improvements).
- **Testing volume halved from FY2024.** Validation and test therefore contain fewer samples per establishment, and history is sparser.
- **Same caveats as Salmonella:**
  - targeted sampling
  - the assumed 7-day result lag
  - history at inference is stale after 2026-06-30
  - exposure bias for small plants
  - optimistic validation, because it was used for selection, calibration and the threshold
