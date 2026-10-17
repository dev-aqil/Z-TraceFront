# Claude Code Prompt: Person B — Food Contamination Risk ML

> **Purpose:** Paste the prompt below into Claude Code in your project repository. You are **Person B**, responsible for modeling, evaluation, explainability, model packaging, and inference. Person A is responsible for data collection and feature engineering.

## Prompt for Claude Code

You are a senior machine learning engineer. Build the **Person B ML component** of a food contamination risk prediction project.

### Project context

We are developing a system that estimates food contamination risk across the **farm → factory → logistics → retail** supply chain.

There are two developers:

- **Person A** owns data ingestion, cleaning, dataset integration, and feature engineering.
- **Person B (me)** owns ML modeling, evaluation, explainability, model packaging, and inference.

You are working on Person B's component. Build a reproducible Python ML project with a proper architecture, documentation, CLI commands, unit tests, and a FastAPI inference endpoint.

### Important scientific constraints

1. Our first model should focus on **USDA FSIS raw poultry Salmonella laboratory sampling data**.
2. **Target:** Whether a sample tested positive for Salmonella, **not** whether a retail batch is proven safe or unsafe.
3. Inspect actual FSIS downloaded files and metadata **before** choosing column names, interpreting positive/negative codes, or declaring the dataset usable.
4. Never invent training data, model evaluation scores, feature availability, download URLs, or contamination labels.
5. Never join unrelated records on food type, state, or date and pretend they represent the same physical batch.
6. Do not use post-sampling data or current lab results as predictors for that sample.
7. Do not use recall status, test outcome, or other target-derived information as a feature.
8. Prefer **temporal splitting** when reliable dates exist. Use a documented fallback otherwise. Never randomly mix duplicated or correlated samples across training and testing.
9. Treat historical establishment positive rates as time-dependent features computed from **strictly earlier observations**, with appropriate smoothing and leakage checks.
10. Do not claim that SHAP identifies causes of contamination.
11. Do not convert a calibrated score into a food-safety certification.
12. Do not combine biological and chemical risk models into one unsupported numerical probability.

### MVP data

Official source:  
https://www.fsis.usda.gov/science-data/data-sets-visualizations/laboratory-sampling-data

Use the **Raw Poultry Sampling** section. Read its metadata and determine the actual sample identifiers, dates, pathogen result fields, establishment fields, and product categories.

If the website or download cannot be accessed:

- Provide a documented manual download procedure.
- Write schema-inspection and validation utilities that work on locally supplied files.
- Clearly mark training as **blocked until genuine data is provided**.
- Do not report synthetic results as real evaluation results.
- A small synthetic fixture is permitted for testing code only and must be clearly marked synthetic.

### Data contract with Person A

Create `docs/data_contract.md` documenting:

- `sample_id`
- `sample_date`
- `establishment_id`, if available
- `product_category`
- Optional metadata known **before** test results
- `salmonella_positive` target
- Strict definitions for missing values, unknown categories, dates, and labels
- Extension schema for future batch-level cold-chain data

Treat these as **canonical internal names only**. Build explicit source-column mappings after checking the real dataset. Do not assume official FSIS files use these field names.

### Deliverables

1. Production-style Python project structure.
2. Dataset loader and schema validation.
3. Exploratory data analysis script.
4. Feature selection and leakage-exclusion logic.
5. Reproducible training/validation/test splitting.
6. Preprocessing using scikit-learn `Pipeline` and `ColumnTransformer`.
7. `DummyClassifier`, Logistic Regression, Random Forest, and XGBoost baselines.
8. Class imbalance handling with justified options.
9. Evaluation metrics: **precision, recall, F1, PR-AUC, ROC-AUC, specificity, confusion matrix, false negative rate, and Brier score**.
10. A model comparison report in CSV and/or JSON.
11. Threshold selection using **validation data only**, with precision/recall trade-offs.
12. Probability calibration assessment, with a calibration procedure if justified.
13. SHAP explanations for the final model, plus global feature importance.
14. A model registry directory with serialized **complete preprocessing + model pipelines** and version metadata.
15. A FastAPI application exposing `GET /health` and `POST /predict`.
16. Prediction JSON containing `model_version`, `pathogen`, `probability_positive`, `risk_band`, `threshold`, and an explanation where supported.
17. Unit tests for loading, invalid schema, splitting, leakage, prediction schema, and inference.
18. A reproducible `README.md` with installation and execution commands.
19. `docs/model_card.md` explaining training provenance, evaluation, bias, scope, and limitations.
20. Example API requests based only on actually supported features.

### Folder structure

```text
food-risk-ml/
├── data/
│   ├── raw/
│   └── processed/
├── configs/
├── docs/
│   ├── data_contract.md
│   └── model_card.md
├── notebooks/
├── src/
│   ├── data/
│   ├── features/
│   ├── models/
│   ├── evaluation/
│   ├── explainability/
│   └── api/
├── tests/
├── artifacts/
├── reports/
├── pyproject.toml
├── README.md
└── .gitignore
```

Make these directories functional, not placeholders. Do not commit large datasets or trained model binaries by default.

### Implementation preferences

- **Python**, pandas, numpy, scikit-learn, XGBoost, SHAP, Pydantic, FastAPI, pytest, joblib, matplotlib.
- Use type hints, logging, configuration, and fixed random seeds.
- Keep the architecture simple enough for a two-person team.
- Avoid unnecessary infrastructure, MLflow servers, Kubernetes, distributed ML, or premature deep learning.

### Workflow

1. **Inspect:** Inspect the existing repository and source dataset availability.
2. **Validate:** Write the project structure, data contract, and dataset validation.
3. **Prepare:** Implement feature processing, chronological splitting, and leakage checks.
4. **Train:** Implement baselines and an experiment runner.
5. **Evaluate:** Implement metrics, threshold tuning, calibration checks, and explainability.
6. **Serve:** Implement the inference API and automated tests.
7. **Verify:** Run tests, linting, and genuine training **if real data exists**.
8. **Report:** Produce an honest completion report, including which items are blocked by missing data.

**Start by inspecting the current repository. Execute work rather than merely proposing it. Make sensible assumptions, document them, and do not fabricate evidence. Keep all Person B implementation inside clearly named modules so Person A can integrate their data pipeline later.**

---

## Person B quick-start checklist

- [ ] Create or clone the Git repository.
- [ ] Obtain the official FSIS raw poultry sampling files and documentation.
- [ ] Agree with Person A on the data contract and which features are available at prediction time.
- [ ] Run dataset validation and exploratory analysis.
- [ ] Train a dummy baseline and Logistic Regression first.
- [ ] Evaluate the temporal holdout using recall, precision, and PR-AUC.
- [ ] Compare Random Forest and XGBoost.
- [ ] Add explanations, threshold tuning, and calibration checks.
- [ ] Package the final preprocessing/model pipeline and expose `/predict`.
- [ ] Document the limitations and pass the API contract to Person A.

**Definition of success for the MVP:** A reproducible, evaluated model that predicts *whether a sampled raw poultry product will test positive for Salmonella* using only valid pre-result features. It does **not** certify food as safe and does **not yet** cover the full supply chain.
