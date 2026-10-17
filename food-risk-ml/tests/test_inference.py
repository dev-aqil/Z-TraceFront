import json

import numpy as np
import pandas as pd
import pytest

from src.models.baselines import xgboost_available
from src.models.predict import Predictor
from src.models.registry import latest_model_dir

REQUIRED_METRICS = {"precision", "recall", "f1", "pr_auc", "roc_auc", "specificity", "false_negative_rate",
                    "brier", "tn", "fp", "fn", "tp"}


def test_training_outputs_are_flagged_synthetic_and_complete(trained):
    root = trained["root"]
    metrics = pd.read_csv(root / "reports" / "metrics.csv")
    assert metrics["synthetic"].all()
    expected = {"dummy_prior", "logistic_regression", "random_forest"} | ({"xgboost"} if xgboost_available() else set())
    assert set(metrics["model"]) == expected
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
    # multithreaded float summation can differ in the last ulp between calls; anything larger is a real bug
    assert [r["probability_positive"] for r in a] == pytest.approx([r["probability_positive"] for r in b], abs=1e-12)
    for r in a:
        assert 0.0 <= r["probability_positive"] <= 1.0
        assert r["risk_band"] == p.risk_band(r["probability_positive"])
        assert (r["risk_band"] == "high") == (r["probability_positive"] >= r["threshold"])
        assert r["trained_on_synthetic_data"] is True


def test_select_model_ties_are_statistical_and_go_to_preference():
    from src.models.train import select_model
    pref = ["xgboost", "logistic_regression", "random_forest"]
    rng = np.random.default_rng(0)
    y = rng.binomial(1, 0.3, 2000)
    signal = y + rng.normal(0, 1.0, len(y))
    # Same signal plus tiny noise: the leader cannot be told apart, so the tie goes to xgboost
    near = {"random_forest": signal + rng.normal(0, 0.05, len(y)), "xgboost": signal}
    best, tied, tests = select_model(y, near, pref, 200, 0)
    assert best == "xgboost" and set(tied) == {"random_forest", "xgboost"}
    # Pure noise for xgboost: a real gap, so the better model wins despite preference
    far = {"random_forest": signal, "xgboost": rng.normal(size=len(y))}
    best, tied, tests = select_model(y, far, pref, 200, 0)
    assert best == "random_forest" and tied == ["random_forest"] and tests["vs_leader"]["xgboost"]["ci"][0] > 0


def test_pinned_model_overrides_selection_and_is_recorded(tmp_path, cfg, synthetic_df):
    from src.models.train import run_training
    rep = run_training(synthetic_df, cfg, tmp_path / "r", tmp_path / "reg", {}, pinned_model="logistic_regression")
    assert rep["selected_model"] == "logistic_regression" and rep["pinned_model"] == "logistic_regression"
    assert "platform_selection" in rep["tie_tests"]
    meta = json.loads((latest_model_dir(tmp_path / "reg") / "metadata.json").read_text())
    assert meta["selection"]["pinned_model"] == "logistic_regression"
    with pytest.raises(ValueError, match="not a candidate"):
        run_training(synthetic_df, cfg, tmp_path / "r2", tmp_path / "reg2", {}, pinned_model="dummy_prior")
