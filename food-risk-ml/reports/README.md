# reports

CLI commands write their output here. Nothing in this folder is real evaluation evidence until a genuine FSIS training run has written it. Check the `synthetic` field in every JSON/CSV.

| File | Written by | Contents |
|---|---|---|
| `schema_inspection_<file>.md/.json` | `inspect` | Columns, missingness, top values, date/numeric parse rates, mapping hints, leakage-denylist hits |
| `eda/` | `eda` | Positive rate by month and by product category, missingness, summary |
| `metrics.csv`, `metrics.json` | `train` | Every model × {val, test}: precision, recall, F1, specificity, FNR, PR-AUC, ROC-AUC, Brier, confusion matrix |
| `thresholds/<model>_val.csv` | `train` | Validation precision/recall/F1 at every candidate threshold |
| `final_model.json` | `train` | Selected model, calibration decision, threshold rule, final val/test metrics, top SHAP features |
| `pr_curves_val.png`, `calibration_test.png`, `shap_importance*.csv/png` | `train` | Plots and SHAP global importance |

PNGs are git-ignored. Regenerate them with the CLI.
