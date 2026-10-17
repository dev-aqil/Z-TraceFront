# artifacts/registry

This is the file-based model registry, written by `python -m src.cli train`. Each version lives in `registry/<pathogen>-<model>-<UTC timestamp>/` and contains:

| File | Contents |
|---|---|
| `model.joblib` | Complete fitted preprocessing + model pipeline (Platt-wrapped if calibration was applied) |
| `metadata.json` | Version, task, provenance (data hashes, git commit, synthetic flag), features, threshold, risk bands, val/test metrics, library versions, config |
| `history.csv` | Per-establishment daily sample/positive counts used for history features at inference |
| `background.csv` | 200 training feature rows (SHAP background) |

`registry/LATEST` names the version the API loads by default.

Model binaries are git-ignored. To share a model, copy the whole version directory. Load it only from a trusted source, because joblib files execute code when loaded.
