# food-risk-ml: Salmonella sample-positivity model (Person B)

This is the ML component of Tracefront. It trains and serves a model that estimates the probability that a **USDA FSIS raw poultry laboratory sample tests positive for Salmonella**, using only information known before the test. It includes leakage-safe features, a chronological evaluation, threshold tuning on validation data only, a calibration check, SHAP explanations, a file-based model registry and a FastAPI endpoint.

> **Current status: trained on real FSIS data (FY2014–FY2026, 325,121 samples).**
> - **Registered model:** `salmonella-xgboost-20261017T062839Z`
> - **Test period (Oct 2024 – Jun 2026):** PR-AUC 0.299 against a 0.098 base rate, ROC-AUC 0.74, recall 0.83, precision 0.14
> - Details and limitations are in [docs/model_card.md](docs/model_card.md).
> - The source mapping is a **draft pending team review**.
>
> The unit tests run on a separate **synthetic fixture** (`tests/synthetic.py`, IDs prefixed `SYNTH-`). Anything trained on it is flagged as synthetic and is never an evaluation result.

The project has three separate ML problem types: biological, chemical and cold-chain/spoilage. This package is the **biological** one. See [docs/data_contract.md](docs/data_contract.md) §1.

## Setup

Requires Python 3.11 or later (tested on 3.13).

```
cd food-risk-ml
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate on Linux/macOS
pip install -e ".[dev,boost,explain]"   # boost = xgboost, explain = shap; both optional (no s390x wheels)
pytest                          # 100 tests on synthetic fixtures
ruff check src tests
```

## Getting the data

The FSIS site blocks scripted downloads (HTTP 403), so download the files in a normal browser:

1. Open https://www.fsis.usda.gov/news-events/publications/raw-poultry-sampling.
2. Download every `raw_poultry_sampling_data_fyNNNN.zip`, FY2014 to the current year, about 30 MB in total.
3. Put the zips in `data/raw/fsis_raw_poultry/zips/`. Each zip holds one JSON file, and the metadata and data dictionary are embedded in that JSON.
4. Build the canonical table:
   ```
   python -m src.cli inspect data/raw/fsis_raw_poultry/zips/raw_poultry_sampling_data_fy2026.zip   # optional profile
   python -m src.cli prepare data/raw/fsis_raw_poultry/zips/*.zip
   ```

`prepare` uses [configs/source_mapping.toml](configs/source_mapping.toml), which quotes the FSIS data dictionary for every choice. It reads only FSIS's **primary** test table. The secondary table (serotype, allele code, PFGE/WGS, AMR) exists only for positives, so it is outcome-derived and never loaded. The output, `data/processed/canonical.csv`, includes the source file hashes.

Other supported inputs: CSV, XLSX, generic JSON (a list of records, or an object with exactly one list of records), and a zip containing exactly one of these.

## Commands

| Command | What it does |
|---|---|
| `python -m src.cli inspect <raw files>` | Schema/value profile and mapping hints → `reports/schema_inspection_*.md` |
| `python -m src.cli prepare <raw files>` | Raw + mapping → dedup → validate → `data/processed/canonical.csv` |
| `python -m src.cli validate <canonical.csv>` | Check a Person A delivery against the contract |
| `python -m src.cli eda [--canonical path]` | Positive rate by month and category, missingness → `reports/eda/` |
| `python -m src.cli train [--canonical path]` | 4 baselines → `reports/metrics.csv`, then calibration, threshold, SHAP, registry |
| `python -m src.cli predict docs/examples/predict_request.json` | Score a request with the latest registered model |
| `uvicorn src.api.app:app --port 8100` | Serve `GET /health` and `POST /predict` |
| `python -m src.cli check-handoff <handoff.json>` | Validate a Person A model-ready handoff against the target contracts (no training) |
| `python -m src.cli experiment <handoff.json>` | Baseline sequence (dummy → linear → RF → HistGradientBoosting → XGBoost if installed) on a validated handoff |
| `python -m src.cli train-chemical` | Imidacloprid detection model from Person A's readiness bundle (hash-pinned, audited split, commodity baseline, paired bootstrap) → `reports/chemical_imidacloprid/`, `artifacts/registry_chemical_imidacloprid/`. Model card: `docs/model_card_chemical_imidacloprid.md` |

All settings (seed, split fractions, label lag, smoothing, imbalance strategy, model parameters, threshold policy) live in [configs/config.toml](configs/config.toml).

## API

```
curl localhost:8100/health
curl -X POST localhost:8100/predict -H "Content-Type: application/json" -d @docs/examples/predict_request.json
```

The request accepts only features the model actually uses: `sample_date`, `product_category`, `establishment_id`, and `metadata` with any `meta_*` features declared at training time. Unknown fields return 422. With no model registered, `/health` reports `no_model` and `/predict` returns 503.

The response contains:
- `model_version`, `pathogen`, `probability_positive`, `threshold`
- `risk_band`: `high`, `medium` or `low`
- `explanation`: top SHAP contributions, with `explanation_units`
- `trained_on_synthetic_data`
- `disclaimer`

The example request uses real values from the training data (a chicken-parts sample at one establishment).

Bands are prioritisation tiers, not safety verdicts. A low score does not mean safe. SHAP shows how the model's score responds to inputs, not causes of contamination.

## Multi-target modeling framework

Biological, chemical and cold-chain targets are separate contracts in [configs/modeling/targets.toml](configs/modeling/targets.toml). **All of them are currently blocked.** `experiment` refuses to run unless:
- Person A's handoff manifest says `model_ready: true`
- its table matches the recorded SHA-256
- the target's status is `READY`
- no feature is a label, an identifier, post-prediction, or matches the target's forbidden patterns

The plans are in the repo-root `reports/`:
- [target contracts](../reports/modeling_target_contracts.md)
- [feature requirements](../reports/modeling_feature_requirements.md)
- [split strategy](../reports/modeling_split_strategy.md)
- [experiment plan](../reports/modeling_experiment_plan.md)
- [LinuxONE compatibility](../reports/linuxone_modeling_compatibility.md)
- [M8 handoff contract](../reports/modeling_m8_handoff_contract.md)

## Layout

```
configs/      config.toml (training), source_mapping.toml (FSIS → canonical, fill after inspection)
src/data/     contract (canonical schema + validation), loader (read/map/dedup), inspect, eda
src/features/ build (features + time-guarded establishment history), split, leakage guards
src/models/   baselines, train (experiment runner), registry, predict
src/evaluation/  metrics + threshold selection, calibration
src/explainability/  SHAP local + global
src/api/      FastAPI app
tests/        unit tests + synthetic fixture (code testing only)
docs/         data_contract.md, model_card.md, examples/
data/raw, data/processed, artifacts/registry, reports/   (contents git-ignored)
notebooks/    exploration notebook that calls the src functions
```

## Integration with Person A

Person A can either deliver raw FSIS files, which this package maps with `prepare`, or deliver `data/processed/canonical.csv` directly following [docs/data_contract.md](docs/data_contract.md). Person A's names `sample_time`, `factory_id`, `food_category` and `pathogen_positive` + `pathogen` are accepted and renamed. Check a delivery with `validate`.

## Key design decisions

| Decision | Why |
|---|---|
| Chronological split with whole days per split | Measures forward-in-time performance and keeps same-day correlated samples together |
| History features count only results with `date + lag < sample_date` | No same-sample, same-day or not-yet-reported labels. Brute-force tested. |
| Class reweighting rather than SMOTE | No synthetic samples, and it works with one-hot features. Calibration is checked afterwards. |
| Threshold chosen on validation; test used once | Unbiased test estimate |
| Platt scaling only if out-of-fold validation Brier improves | Avoids calibrating noise |
| Cross-source joins (FDA, openFDA, RASFF) excluded | No verified entity key to FSIS establishments ([data contract](docs/data_contract.md) §5) |

`dummy_prior` is the floor every model must beat. See [docs/model_card.md](docs/model_card.md) for scope and limitations.
