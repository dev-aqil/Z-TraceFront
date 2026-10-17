"""Native explainers (used on every platform, incl. s390x without shap) must equal the shap library's values."""

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from src.explainability import shap_explain
from src.features.build import build_preprocessor
from src.models.baselines import XGBClassifier, make_pipeline
from tests.synthetic import make_synthetic_canonical

try:
    import shap
except ImportError:  # s390x: only the no-shap test runs
    shap = None
needs_shap = pytest.mark.skipif(shap is None, reason="shap not installed")
CAT, NUM = ["product_category", "establishment_id"], ["meta_num_synthetic_score"]


def _fit(model):
    df = make_synthetic_canonical(800, seed=3)
    X, y = df[CAT + NUM], df["pathogen_positive"].astype(int).to_numpy()
    X.loc[X.index[::7], "meta_num_synthetic_score"] = np.nan  # exercise imputation + missing indicators
    return make_pipeline(build_preprocessor(CAT, NUM, 10), model).fit(X, y), X


@needs_shap
@pytest.mark.skipif(XGBClassifier is None, reason="xgboost not installed")
def test_xgboost_native_equals_shap_tree_explainer():
    pipe, X = _fit(XGBClassifier(n_estimators=40, max_depth=3, random_state=0))
    native = shap_explain.Explainer(pipe, X.iloc[:100]).values(X.iloc[:50])
    Xt = pipe.named_steps["preprocess"].transform(X.iloc[:50])
    ref = np.asarray(shap.TreeExplainer(pipe.named_steps["model"]).shap_values(Xt))
    np.testing.assert_allclose(native, ref, atol=1e-5)


@needs_shap
def test_linear_native_equals_shap_linear_explainer():
    pipe, X = _fit(LogisticRegression(max_iter=500))
    pre = pipe.named_steps["preprocess"]
    native = shap_explain.Explainer(pipe, X.iloc[:100]).values(X.iloc[:50])
    lin = shap.LinearExplainer(pipe.named_steps["model"], pre.transform(X.iloc[:100]))
    ref = lin.shap_values(pre.transform(X.iloc[:50]))
    np.testing.assert_allclose(native, np.asarray(ref), atol=1e-8)


@pytest.mark.skipif(XGBClassifier is None, reason="xgboost not installed")
def test_explanations_work_without_shap_package(monkeypatch):
    monkeypatch.setattr(shap_explain, "shap", None)  # as on s390x
    pipe, X = _fit(XGBClassifier(n_estimators=20, max_depth=3, random_state=0))
    e = shap_explain.Explainer(pipe, X.iloc[:100])
    assert e.supported and e.units == "log-odds"
    top = e.local(X.iloc[:2], top_k=3)
    assert len(top) == 2 and all(1 <= len(t) <= 3 for t in top)
