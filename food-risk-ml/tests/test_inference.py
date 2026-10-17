import json

import pandas as pd

from src.models.predict import Predictor
from src.models.registry import latest_model_dir

REQUIRED_METRICS = {"precision", "recall", "f1", "pr_auc", "roc_auc", "specificity", "false_negative_rate",
                    "brier", "tn", "fp", "fn", "tp"}


def test_training_outputs_are_flagged_synthetic_and_complete(trained):
    root = trained["root"]
    metrics = pd.read_csv(root / "reports" / "metrics.csv")
    assert metrics["synthetic"].all()
    assert set(metrics["model"]) == {"dummy_prior", "logistic_regression", "random_forest", "xgboost"}
    assert REQUIRED_METRICS <= set(metrics.columns)
    meta = json.loads((latest_model_dir(root / "registry") / "metadata.json").read_text())
    assert meta["provenance"]["synthetic"] is True
    assert meta["task"] == "biological_pathogen_positive"
    assert meta["split"]["method"] == "temporal"
    assert meta["risk_bands"]["medium_from"] <= meta["risk_bands"]["high_from"]


def test_predictor_outputs_valid_deterministic_scores(trained):
    p = Predictor(latest_model_dir(trained["root"] / "registry"))
    reqs = [{"sample_date": "2024-02-01", "product_category": "synthetic_ground", "establishment_id": "SYNTH-EST-001"},
            {"sample_date": "2024-02-01", "product_category": "never_seen_category"}]
    a, b = p.predict(reqs), p.predict(reqs)
    assert [r["probability_positive"] for r in a] == [r["probability_positive"] for r in b]
    for r in a:
        assert 0.0 <= r["probability_positive"] <= 1.0
        assert r["risk_band"] == p.risk_band(r["probability_positive"])
        assert (r["risk_band"] == "high") == (r["probability_positive"] >= r["threshold"])
        assert r["trained_on_synthetic_data"] is True
