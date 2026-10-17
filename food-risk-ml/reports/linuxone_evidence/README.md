# LinuxONE (IBM Z) training evidence — 2026-10-17

These are raw logs copied unchanged from the LinuxONE Community Cloud VM (`ibmdatatontest`, `~/tracefront-evidence/`). Every step was run through `run_step.sh`, which writes a header (UTC time, host, kernel, architecture, OS, Python, byte order) and the `/usr/bin/time -v` resource usage.

| Log | What it shows |
|---|---|
| `00_hardware.log` | `s390x`, big-endian, IBM machine type 9175 under z/VM 7.3, 3 CPUs at 5.5 GHz. CPU flags include `nnpa` (on-chip AI accelerator) and vector extensions. |
| `01_apt_install.log` | ML stack installed from Ubuntu 24.04 s390x packages (numpy 1.26.4, pandas 2.1.4, scikit-learn 1.4.1, xgboost 2.0.3) |
| `02_venv.log` | Venv reusing those packages; pydantic v2 installed from an s390x wheel |
| `03_verify_data.log` | All 13 FSIS raw-poultry zips match the SHA-256 recorded at download |
| `04_tests_s390x.log` | Full test suite on IBM Z: 90 passed |
| `05_prepare.log` | 13 FSIS fiscal years → 325,121 canonical rows in 15 s (same count as on x86) |
| `06_train.log` | Four models trained, XGBoost selected, Platt calibration applied, model registered. 1 min 16 s wall time, 1.4 GB peak RAM. |
| `07_api.log` | FastAPI served the LinuxONE-trained model on the VM's localhost: `/health` OK and a `/predict` response |
| `final_model.json`, `metrics.csv`, `registry_metadata.json` | Results and provenance of model `salmonella-xgboost-20261017T101927Z` (test PR-AUC 0.301, ROC-AUC 0.739; library versions recorded) |

No SHAP explanation was produced on the VM: SHAP has no s390x package, so the response's `explanation` is null.
