# LinuxONE (IBM Z) evidence: beef and RTE models, chemical XGBoost, explanations on IBM Z, cold chain (2026-10-17)

Raw logs copied unchanged from the LinuxONE Community Cloud VM (`ibmdatatontest`, `~/tracefront-evidence/step4/`). The hardware is as in `../00_hardware.log`: `s390x`, big-endian, IBM 9175, Ubuntu 24.04.5, Python 3.12.3, scikit-learn 1.4.1, xgboost 2.0.3. **SHAP is not installed** (no s390x package). Each step ran through `../run_step.sh` with `/usr/bin/time -v`.

**Code state:** the working tree on top of commit `9f5f278`, **uncommitted** at the time of the run. The SHA-256 of each code tarball is in `40_code.log` and `48_code_update.log`, and the stage scripts are in this folder. The data tarball holds the beef and RTE zips.

| Log | What it shows |
|---|---|
| `41_verify_data.log` | All 26 beef and RTE zips match their download SHA-256: 0 mismatched |
| `42_tests_s390x.log`, `49_tests_s390x.log` | **112 / 113 passed, 2 skipped.** The skips are the two tests that compare against the SHAP library. The test of explanations **without** SHAP passed. |
| `43_prepare_*.log` | Same canonical row counts as x86: beef 232,362, RTE 266,030 |
| `44_train_*.log`, `45_train_chemical.log` | Each model trained and registered on IBM Z: beef Salmonella 53 s, STEC 51 s, RTE Listeria 99 s (1.3 GB peak), chemical 19 s |
| `46_cold_chain.log` | Cold-chain rules on a **SIMULATED** compressor failure: excursion, then critical. Benchmark: **269,141 readings/s, 3.7 µs per reading** (x86 laptop: about 136,000/s). |
| `47_api.log`, `51_api_beef_stec_pinned.log` | FastAPI on localhost for each pathogen model. **Explanations are returned on IBM Z**, through XGBoost's built-in TreeSHAP. Median request latency 90–134 ms over 20 calls. |
| `final_model_*.json`, `metrics_*.csv` | Results and provenance per model |

## IBM Z vs x86, test period

| Model | x86 PR-AUC / ROC-AUC | s390x PR-AUC / ROC-AUC |
|---|---|---|
| Beef Salmonella | 0.058 / 0.723 | 0.058 / 0.724 |
| RTE Listeria | 0.032 / 0.760 | 0.032 / 0.770 |
| Chemical imidacloprid | 0.158 / 0.845 | 0.151 / 0.843 |
| Beef STEC (XGBoost, pinned) | 0.018 / 0.630 | 0.011 / 0.629 |

## Finding: a borderline model choice flipped between platforms (beef STEC)

The selection rule treats two models as tied when a paired-bootstrap 95% interval of their validation PR-AUC difference includes 0. For STEC (0.3% positives) the interval sits on the boundary:
- **x86:** forest minus XGBoost CI [−0.0008, +0.042], so tied, and XGBoost was chosen.
- **s390x:** xgboost 2.0.3 gave a validation PR-AUC of 0.0104 instead of 0.0110, the CI moved to [+0.0014, +0.042], so not tied, and the forest was chosen (`44_train_beef_stec.log`). That forest returned no explanation on IBM Z.

**Fix:** model choice is made once, on the reference platform, and the target platform retrains that model type. The new `train --model <type>` option does this and records the pin in the model metadata. `50_train_beef_stec_pinned.log` shows `PINNED xgboost (this platform's own selection would be random_forest)`. The forest registration is kept in the VM registry as evidence; the pinned XGBoost one is `LATEST`. The other three models chose the same type on both platforms.

The lower STEC test PR-AUC on s390x (0.011 vs 0.018, same ROC-AUC) comes from the xgboost version: with 115 test positives, small ranking changes move PR-AUC a lot.
