"""Baseline models and complete preprocessing+model pipelines.

Class imbalance: positives are expected to be a minority. The default strategy is class reweighting
(balanced class_weight for LR/RF/HGB, scale_pos_weight=neg/pos for XGBoost). It is preferred over resampling
(e.g. SMOTE) because it creates no artificial samples, works with one-hot categoricals and keeps the
pipeline simple. Reweighting inflates raw probabilities, so calibration is assessed afterwards and the
decision threshold is tuned on validation data either way. "none" is available for comparison.

XGBoost is optional: there are no s390x wheels on PyPI (reports/linuxone_modeling_compatibility.md), so every
sequence works without it and scikit-learn's HistGradientBoosting is the portable gradient-boosting baseline.
LightGBM is deliberately not offered.
"""

import logging
from typing import Any

import numpy as np
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline

log = logging.getLogger(__name__)

try:
    from xgboost import XGBClassifier, XGBRegressor
except ImportError:  # ponytail: optional on s390x; install a distro/source build to enable
    XGBClassifier = XGBRegressor = None


def xgboost_available() -> bool:
    return XGBClassifier is not None


def build_models(cfg: dict[str, Any], y_train: np.ndarray, seed: int) -> dict[str, Any]:
    """FSIS Salmonella model set (src/models/train.py)."""
    weighted = cfg["imbalance"]["strategy"] == "class_weight"
    pos = max(int(np.sum(y_train)), 1)
    neg = len(y_train) - pos
    m = cfg["models"]
    models = {
        "dummy_prior": DummyClassifier(strategy="prior"),
        "logistic_regression": LogisticRegression(
            **m["logistic_regression"], class_weight="balanced" if weighted else None, random_state=seed),
        "random_forest": RandomForestClassifier(
            **m["random_forest"], class_weight="balanced_subsample" if weighted else None, random_state=seed),
    }
    if xgboost_available():
        models["xgboost"] = XGBClassifier(
            **m["xgboost"], scale_pos_weight=neg / pos if weighted else 1.0, tree_method="hist",
            eval_metric="aucpr", random_state=seed, n_jobs=-1)
    else:
        log.warning("xgboost not installed: skipping it")
    return models


def baseline_sequence(task_type: str, y_train: np.ndarray, seed: int, weighted: bool = True,
                      use_xgboost: bool = True) -> dict[str, Any]:
    """Incremental baselines for any target contract: dummy -> linear -> random forest -> HistGradientBoosting
    -> XGBoost (only if installed and enabled)."""
    if task_type == "regression":
        models = {"dummy_mean": DummyRegressor(strategy="mean"), "ridge": Ridge(alpha=1.0),
                  "random_forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=5, n_jobs=-1,
                                                         random_state=seed),
                  "hist_gradient_boosting": HistGradientBoostingRegressor(random_state=seed)}
        if use_xgboost and xgboost_available():
            models["xgboost"] = XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05, tree_method="hist",
                                             random_state=seed, n_jobs=-1)
        return models
    if task_type not in ("binary", "multiclass"):
        raise ValueError(f"unknown task_type {task_type!r}")
    cw = "balanced" if weighted else None
    models = {"dummy_prior": DummyClassifier(strategy="prior"),
              "logistic_regression": LogisticRegression(max_iter=2000, class_weight=cw, random_state=seed),
              "random_forest": RandomForestClassifier(n_estimators=300, min_samples_leaf=5, n_jobs=-1,
                                                      class_weight="balanced_subsample" if weighted else None,
                                                      random_state=seed),
              "hist_gradient_boosting": HistGradientBoostingClassifier(class_weight=cw, random_state=seed)}
    if use_xgboost and xgboost_available():
        extra = {}
        if task_type == "binary" and weighted:
            pos = max(int(np.sum(y_train)), 1)
            extra["scale_pos_weight"] = (len(y_train) - pos) / pos
        models["xgboost"] = XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05, tree_method="hist",
                                          random_state=seed, n_jobs=-1, **extra)
    return models


def make_pipeline(preprocessor: ColumnTransformer, estimator: Any) -> Pipeline:
    return Pipeline([("preprocess", clone(preprocessor)), ("model", estimator)])
