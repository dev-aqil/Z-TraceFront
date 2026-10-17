"""Baseline classifiers and complete preprocessing+model pipelines.

Class imbalance: positives are expected to be a minority. The default strategy is class reweighting
(balanced class_weight for LR/RF, scale_pos_weight=neg/pos for XGBoost). It is preferred over resampling
(e.g. SMOTE) because it creates no artificial samples, works with one-hot categoricals and keeps the
pipeline simple. Reweighting inflates raw probabilities, so calibration is assessed afterwards and the
decision threshold is tuned on validation data either way. "none" is available for comparison.
"""

from typing import Any

import numpy as np
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier


def build_models(cfg: dict[str, Any], y_train: np.ndarray, seed: int) -> dict[str, Any]:
    weighted = cfg["imbalance"]["strategy"] == "class_weight"
    pos = max(int(np.sum(y_train)), 1)
    neg = len(y_train) - pos
    m = cfg["models"]
    return {
        "dummy_prior": DummyClassifier(strategy="prior"),
        "logistic_regression": LogisticRegression(
            **m["logistic_regression"], class_weight="balanced" if weighted else None, random_state=seed),
        "random_forest": RandomForestClassifier(
            **m["random_forest"], class_weight="balanced_subsample" if weighted else None, random_state=seed),
        "xgboost": XGBClassifier(
            **m["xgboost"], scale_pos_weight=neg / pos if weighted else 1.0, tree_method="hist",
            eval_metric="aucpr", random_state=seed, n_jobs=-1),
    }


def make_pipeline(preprocessor: ColumnTransformer, estimator: Any) -> Pipeline:
    return Pipeline([("preprocess", clone(preprocessor)), ("model", estimator)])
