# LinuxONE (IBM Z) evidence: imidacloprid chemical model, 2026-10-17

Raw logs copied unchanged from the LinuxONE Community Cloud VM (`ibmdatatontest`, `~/tracefront-evidence/chemical/`). The hardware is as in `../00_hardware.log`: `s390x`, big-endian, IBM 9175, Ubuntu 24.04.5. Each step ran through `../run_step.sh` with `/usr/bin/time -v`. The stage script is `stage_chem.sh`.

| Log | What it shows |
|---|---|
| `20_code.log` | Code **and Person A's handoff files** come from a `git archive` of commit `6513e9f`, which gives the exact committed bytes. SHA-256 of every handoff file is listed. They equal Person A's pins in the readiness file (dataset `686885fa…`, feature manifest `ced00126…`, leakage audit `4056852c…`). |
| `21_check_handoff.log` | The gate passes on IBM Z: `model_ready` true, all hash pins verified, target contract READY, 9,871 labelled rows, 7 features |
| `22_tests_s390x.log` | Full test suite: **100 passed** |
| `23_train.log` | Audited split reproduced, five candidates fitted, random forest selected, Platt applied, model registered. **18 s wall time, 0.2 GB peak RAM.** |
| `final_model.json`, `metrics.csv`, `registry_metadata.json` | Results and provenance of the s390x model |

## IBM Z vs x86 laptop (same commit, same bytes)

| Test period (46 detections) | x86 (sklearn 1.9.1) | s390x (sklearn 1.4.1) |
|---|---|---|
| Selected model | random forest | random forest |
| PR-AUC | 0.161 | 0.161 |
| ROC-AUC | 0.859 | 0.859 |
| Recall at 10% budget | 0.517 | 0.517 |
| Paired PR-AUC gain vs commodity baseline | +0.057 [+0.023, +0.124] | +0.057 [+0.023, +0.124] |
| Brier (calibrated) | 0.029 | 0.029 |

The random forest gives the same results on both architectures. XGBoost differs slightly (test PR-AUC 0.158 on x86, 0.151 on s390x) because xgboost 3.4.1 and 2.0.3 differ; it was not selected on either machine.

There is no SHAP on the VM, because SHAP has no s390x package.
