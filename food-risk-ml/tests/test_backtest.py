import copy

import numpy as np
import pandas as pd
import pytest

from src.evaluation.backtest import fold_windows, run_backtest
from src.evaluation.metrics import bootstrap_ci, recall_at_budget
from tests.synthetic import make_synthetic_canonical


def test_recall_at_budget_toy():
    y = np.array([1, 0, 1, 0, 0, 0, 0, 0, 0, 1])
    p = np.array([.9, .8, .7, .1, .1, .1, .1, .1, .1, .05])
    r = recall_at_budget(y, p, 0.3)  # top 3 = .9, .8, .7 -> 2 of 3 positives
    assert r["recall"] == pytest.approx(2 / 3) and r["precision"] == pytest.approx(2 / 3)
    assert r["lift"] == pytest.approx((2 / 3) / 0.3)


def test_recall_at_budget_handles_ties_independent_of_row_order():
    # A constant scorer catches exactly the budget share in expectation, whatever the row order.
    y = np.array([1] * 10 + [0] * 90)
    p = np.full(100, 0.1)
    assert recall_at_budget(y, p, 0.2)["recall"] == pytest.approx(0.2)
    assert recall_at_budget(y[::-1], p, 0.2)["recall"] == pytest.approx(0.2)


def test_bootstrap_ci_brackets_point_estimate_and_is_deterministic():
    rng = np.random.default_rng(0)
    y = rng.binomial(1, 0.2, 500)
    p = y * 0.3 + rng.random(500)
    point = recall_at_budget(y, p, 0.2)["recall"]
    ci = bootstrap_ci(lambda a, b: recall_at_budget(a, b, 0.2)["recall"], y, p, n=100, seed=1)
    assert ci[0] <= point <= ci[1]
    assert ci == bootstrap_ci(lambda a, b: recall_at_budget(a, b, 0.2)["recall"], y, p, n=100, seed=1)


def test_fold_inside_sealed_period_is_refused():
    with pytest.raises(ValueError, match="sealed"):
        fold_windows(["2024-11-01"], 12, pd.Timestamp("2024-10-11"))


def test_backtest_never_touches_sealed_rows_and_trains_only_on_the_past(cfg, tmp_path, monkeypatch):
    c = copy.deepcopy(cfg)
    c["backtest"].update(sealed_test_start="2023-07-01", fold_starts=["2022-01-01", "2022-07-01"], fold_months=6,
                         bootstrap=20, min_programme_rows=50)
    df = make_synthetic_canonical()
    seen = []
    import src.evaluation.backtest as bt
    real = bt.make_features
    monkeypatch.setattr(bt, "make_features", lambda d, *a, **k: (seen.append(d["sample_date"].max()), real(d, *a, **k))[1])
    res = run_backtest(df, c, tmp_path, "test", models=["dummy_prior", "logistic_regression"])
    assert max(seen) < pd.Timestamp("2023-07-01")  # no sealed row was ever featurised
    assert res["synthetic"] is True and len(res["folds"]) == 2
    for r in res["runs"]:
        lo, hi = r["pr_auc_ci"]
        assert lo <= r["pr_auc"] <= hi and r["train_rows"] > 0
    assert {"logistic_regression", "dummy_prior"} == {s["model"] for s in res["summary"]}
    assert (tmp_path / "backtest_test.json").exists()
