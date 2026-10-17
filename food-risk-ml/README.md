# food-risk-ml: Salmonella sample-positivity model (Person B)

This is the ML component of Tracefront. It trains and serves a model that estimates the probability that a **USDA FSIS raw poultry laboratory sample tests positive for Salmonella**, using only information known before the test. It includes leakage-safe features, a chronological evaluation, threshold tuning on validation data only, a calibration check, SHAP explanations, a file-based model registry and a FastAPI endpoint.

> **Current status: training is BLOCKED on data.** The FSIS website returned `HTTP 403 Access Denied` (Akamai) to every automated request from the build machine, including the PDFs, so the real files and metadata could not be inspected. The pipeline, tests and API run end to end on a **synthetic test fixture** (`tests/synthetic.py`, IDs prefixed `SYNTH-`). Synthetic runs are flagged in every output and are **not** evaluation results. `configs/source_mapping.toml` is intentionally unfilled, and `prepare` refuses to run until it is filled.

The project has three separate ML problem types: biological, chemical and cold-chain/spoilage. This package is the **biological** one. See [docs/data_contract.md](docs/data_contract.md) §1.

## Setup

Requires Python 3.11 or later (tested on 3.13).

```
cd food-risk-ml
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate on Linux/macOS
pip install -e ".[dev]"
pytest                          # 46 tests on synthetic fixtures
ruff check src tests
```

## Getting the data (manual download)

1. Open https://www.fsis.usda.gov/science-data/data-sets-visualizations/laboratory-sampling-data in a normal browser. Automated downloads were blocked.
2. In the **Raw Poultry Sampling** section, download every data file offered, both current and archived. The data.gov catalogue entry says the dataset is split by fiscal year, with current data refreshed quarterly and the archive annually. The page reportedly offers a JSON view; this is unverified, so take whatever formats are actually listed. Also download the **metadata / data documentation** for the dataset. FSIS asks users to review it before analysis.
3. Save everything with the original filenames in `data/raw/`. Write down the URL and the download date.
4. Profile the files:
   ```
   python -m src.cli inspect data/raw/<file1> data/raw/<file2>
   ```
   Then read `reports/schema_inspection_<file>.md` **alongside the official metadata**.
5. Fill `configs/source_mapping.toml`:
   - sample id, **collection** date column and date format, establishment column, product category column
   - the **Salmonella** result column, and the exact positive and negative codes
   - `verified_by` and `verified_against`

   Every row is tested for several pathogens (for example Campylobacter). Map only the Salmonella result. The other results are same-sample lab results, so they are forbidden as features.
6. Build the canonical table:
   ```
   python -m src.cli prepare data/raw/<file1> data/raw/<file2>
   ```
   This writes `data/processed/canonical.csv` and its provenance file. Files are stacked only if their columns are identical.

Supported formats: CSV, XLSX, JSON (a list of records, or an object with exactly one list of records), and a zip containing exactly one of these.

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

The example request contains placeholders. Replace them with values that appear in the real training data.

Bands are prioritisation tiers, not safety verdicts. A low score does not mean safe. SHAP shows how the model's score responds to inputs, not causes of contamination.

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
