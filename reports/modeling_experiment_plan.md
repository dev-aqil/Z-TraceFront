# Modeling experiment plan — metrics, baselines, reproducibility, explainability

Status date: 2026-10-17. Owner: Person B. Planning only. No model is trained on Person A's M1/M2 outputs. Code: `food-risk-ml/src/models/experiment.py`, run with `python -m src.cli experiment <handoff.json>`. It refuses to run without a model-ready handoff.

## 1. Metrics

### Binary contamination and detection targets

Accuracy is **not** reported as a primary metric. At a 10% positive rate, predicting "negative" for everything scores 90% accuracy and catches nothing.

| Metric | Role |
|---|---|
| **Recall (sensitivity)** and **false-negative rate** | Primary operational metrics. A false negative is a contaminated sample the model ranked low; if inspection effort follows the ranking, it is never looked at. A false positive costs extra inspection effort. |
| **PR-AUC** | Primary ranking metric under imbalance; compared against prevalence (the dummy's PR-AUC) |
| Precision, F1, specificity | Reported at the chosen operating threshold |
| ROC-AUC | Secondary; optimistic under heavy imbalance |
| Brier score + reliability diagram | Calibration: are the probabilities usable as probabilities? |
| Confusion matrix | Always reported with counts |
| Share of samples flagged at the threshold | Workload. "80% recall" means little if it flags 60% of samples. |

**Thresholds** come from validation data only. Default policy: the highest precision with recall ≥ target (0.80 for pathogen targets). The full precision/recall/flag-rate table is reported so the team can choose an operating point.

### Regression targets (`microbial_count`, `residue_concentration`)

MAE and RMSE in target units (log10 CFU; log ppm among detections), R² where variance allows, and residual analysis: mean bias, 5th/95th residual percentiles, and residuals against prediction and against key features. Censored nondetects are handled by the agreed censoring policy, never by silent zero-filling.

### Multiclass (`spoilage_class`)

Macro-F1, balanced accuracy, **per-class recall** (a missed "spoiled" class matters regardless of its frequency), and the confusion matrix. Ordinal error is also reported where classes are ordered.

## 2. Class imbalance

| Option | Use |
|---|---|
| **Class reweighting** (default) | `class_weight="balanced"` for LR, RF and HistGradientBoosting; `scale_pos_weight = neg/pos` for XGBoost. Creates no synthetic rows, works with one-hot categoricals. |
| No reweighting + threshold tuning | Comparison arm. Probabilities stay closer to calibrated. |
| Resampling (SMOTE etc.) | Not used: it fabricates rows, interacts badly with categoricals and grouped data, and distorts probabilities |
| Calibration | Platt scaling fit on validation scores, applied only if out-of-fold validation Brier improves (reweighting inflates raw probabilities) |

## 3. Baseline sequence

Each step must beat the previous one on the validation primary metric to justify its complexity.

| # | Model | Package | s390x status | Notes |
|---|---|---|---|---|
| 1 | Dummy (prior rate / mean) | scikit-learn | likely supported | The floor: PR-AUC = prevalence |
| 2 | Logistic regression / Ridge | scikit-learn | likely supported | Coefficients are directly interpretable |
| 3 | Random forest | scikit-learn | likely supported | Non-linear, robust |
| 4 | **HistGradientBoosting** | scikit-learn | likely supported | **The portable gradient-boosting baseline**; no extra native package |
| 5 | XGBoost | `xgboost` (optional extra) | requires a distro package or source build | Only if installed on the target; the runner skips it otherwise |
| 6 | LightGBM | — | avoid | No s390x wheel, no Debian package, CMake build; not offered |

Fallback if no gradient-boosting library is available: step 4 is already pure scikit-learn. The same pipeline (`ColumnTransformer` with one-hot encoding, median imputation with missing indicators, scaling) feeds every model.

## 4. Reproducibility (implemented in `src/models/contracts.py`)

Each run records two blocks.

**Experiment definition** (hashed into a deterministic `experiment_id`, so the same experiment on x86_64 and s390x shares an ID):
- dataset ID, dataset version, dataset SHA-256 (verified against the file)
- feature-list SHA-256 (sorted names and dtypes)
- target, analyte, target-contract SHA-256
- split definition (method, fractions, time and group columns)
- random seed, model type, full hyperparameters
- threshold rule

**Run environment** (recorded, not hashed):
- training timestamp (UTC), Python version
- `platform.machine()` (e.g. `s390x`), byte order (`big` on s390x), platform string
- scikit-learn and pandas versions

Output goes to `artifacts/experiments/<target>-<dataset hash>/experiment.json`. A test checks that the definition is deterministic.

## 5. Explainability plan (not executed on real handoffs yet)

| Method | Applies to | Portable on s390x? | Notes |
|---|---|---|---|
| Coefficients (standardised features) | Logistic / Ridge | yes (scikit-learn) | Signs and magnitudes on the log-odds scale |
| Permutation importance on validation | Any model | yes (scikit-learn) | Model-agnostic; preferred global method on LinuxONE |
| Impurity (tree) importance | RF / HGB / XGB | yes | Biased toward high-cardinality features; reported only next to permutation importance |
| XGBoost native contributions (`pred_contribs=True`) | XGBoost | where xgboost is installed | Exact TreeSHAP values without the `shap` package |
| `shap` package | LR, trees | requires a source build (C extension) | Used where installed (currently in the FSIS pipeline); optional elsewhere |

Per-prediction output format, with wording fixed:

```
Risk score: 0.81   (band: high; threshold 0.06)
Largest model contributions:
  + temperature excursion minutes      (raised the score)
  + previous establishment positives   (raised the score)
  − storage duration                   (lowered the score)
These are contributions to the model's score, not causes of contamination.
```

Never "X caused contamination". Use "model contribution", "associated with a higher score".
