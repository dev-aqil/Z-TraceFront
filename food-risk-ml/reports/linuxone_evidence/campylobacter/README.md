# LinuxONE (IBM Z) evidence: Campylobacter model, 2026-10-17

Raw logs copied unchanged from the LinuxONE Community Cloud VM (`ibmdatatontest`, `~/tracefront-evidence/campylobacter/`). The hardware and OS are the same as in the Salmonella run (`../00_hardware.log`): `s390x`, big-endian, IBM 9175, Ubuntu 24.04.5.

Each step ran through `../run_step.sh`, which records UTC time, host, architecture, Python and byte order, and `/usr/bin/time -v` resource use. The stage scripts are `stage_campy.sh` and `stage_campy_api.sh`.

| Log | What it shows |
|---|---|
| `10_code.log` | Code is a `git archive` of commit `9e88069`, with tarball SHA-256 recorded. The previous Salmonella copy was moved aside, not overwritten. |
| `11_verify_data.log` | All 13 FSIS zips match the SHA-256 recorded at download |
| `12_tests_s390x.log` | Full test suite on IBM Z: **93 passed** |
| `13_prepare.log` | 325,121 canonical rows; 133,990 without an enrichment result excluded (same counts as on x86) |
| `14_train.log` | Same split as x86 (132,842 / 32,490 / 25,799). XGBoost selected by the tie rule, Platt applied, model registered. **33 s wall time, 0.9 GB peak RAM.** |
| `15_api.log` | FastAPI with `FOOD_RISK_PATHOGEN=campylobacter` on localhost: `/health` OK, `/predict` answered in **0.098 s** |
| `final_model.json`, `metrics.csv`, `registry_metadata.json` | Results and provenance of `campylobacter-xgboost-20261017T131153Z` |

## IBM Z vs x86 laptop (same code, data and split)

| | x86 (sklearn 1.9.1, xgboost 3.4.1) | s390x (sklearn 1.4.1, xgboost 2.0.3) |
|---|---|---|
| Test PR-AUC | 0.434 | 0.433 |
| Test ROC-AUC | 0.752 | 0.752 |
| Test recall / precision at the validation threshold | 0.768 / 0.314 | 0.770 / 0.312 |
| Calibrated Brier | 0.137 | 0.137 |

The small differences come from the library versions and floating-point order, not from the data. The model was retrained on the VM rather than copied, because pickles are not portable across these versions.

On s390x all three learned models were within 0.005 validation PR-AUC (LR 0.429, XGB 0.432, RF 0.434), so the tie rule picked XGBoost there too.

There is no SHAP explanation on the VM: SHAP has no s390x package, so `explanation` is null.
