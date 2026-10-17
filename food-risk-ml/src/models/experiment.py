"""Generic baseline experiment for any target contract, run only on a validated Person A handoff.

Calibration, SHAP and model registration are deliberately not repeated here: once a target's baselines are
compared, the selected model follows the same path as the FSIS pipeline (src/models/train.py).
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.contract import UNKNOWN_CATEGORY
from src.evaluation import splits
from src.evaluation.metrics import binary_metrics, choose_threshold, multiclass_metrics, regression_metrics
from src.features.build import build_preprocessor
from src.models.baselines import baseline_sequence, make_pipeline
from src.models.contracts import Handoff, experiment_definition, load_handoff, run_environment

log = logging.getLogger(__name__)
TRAIN_FRAC, VAL_FRAC = 0.70, 0.15


def split_handoff(h: Handoff, seed: int, overrides: dict | None = None) -> tuple[dict[str, pd.DataFrame], dict]:
    c, m, o = h.contract, h.manifest, overrides or {}
    method, time_col = o.get("method", c["split"]), m["prediction_time_column"]
    group_col = o.get("group_column", c.get("group_column"))
    split_def = {"method": method, "train_frac": TRAIN_FRAC, "val_frac": VAL_FRAC, "time_column": time_col}
    if method == "temporal":
        parts = splits.temporal_split(h.table, time_col, TRAIN_FRAC, VAL_FRAC)
        splits.assert_split_integrity(parts, time_col=time_col)
    elif method == "grouped":
        if group_col not in h.table:
            raise splits.SplitError(f"grouped split needs group column {group_col!r} in the handoff")
        parts = splits.grouped_split(h.table, group_col, TRAIN_FRAC, VAL_FRAC, seed)
        splits.assert_split_integrity(parts, group_col=group_col)
        split_def["group_column"] = group_col
    elif method == "geographic":
        parts = splits.geographic_holdout(h.table, o["region_column"], o["test_regions"], o["val_regions"])
        split_def.update({k: o[k] for k in ("region_column", "test_regions", "val_regions")})
    elif method == "random":
        parts = splits.random_split(h.table, h.target, TRAIN_FRAC, VAL_FRAC, seed, o.get("allow_random", False))
    else:
        raise splits.SplitError(f"unknown split method {method!r}")
    for name, part in parts.items():
        if len(part) == 0 or (c["task_type"] != "regression" and part[h.target].nunique() < 2):
            raise splits.SplitError(f"{name} split has {len(part)} rows or a single class")
    if group_col in h.table and method != "grouped":  # diagnostic: how much of test comes from unseen groups
        seen = set(parts["train"][group_col].dropna())
        split_def["test_rows_from_unseen_groups"] = float((~parts["test"][group_col].isin(seen)).mean())
    return parts, split_def


def feature_matrix(h: Handoff, df: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for f in h.manifest["features"]:
        col = df[f["name"]]
        X[f["name"]] = col.astype(float) if f["dtype"] == "numeric" else col.fillna(UNKNOWN_CATEGORY).astype(str)
    return X


def run_experiment(manifest_path: str | Path, out_dir: str | Path, seed: int = 42, targets: dict | None = None,
                   split_overrides: dict | None = None, use_xgboost: bool = True) -> dict:
    h = load_handoff(manifest_path, targets)  # refuses anything not model-ready
    c, task = h.contract, h.contract["task_type"]
    parts, split_def = split_handoff(h, seed, split_overrides)
    X = {k: feature_matrix(h, v) for k, v in parts.items()}
    y = {k: v[h.target].to_numpy() for k, v in parts.items()}
    cat = [f["name"] for f in h.manifest["features"] if f["dtype"] != "numeric"]
    num = [f["name"] for f in h.manifest["features"] if f["dtype"] == "numeric"]
    pre = build_preprocessor(cat, num, min_category_count=10)
    labels = sorted(np.unique(y["train"]).tolist()) if task == "multiclass" else None

    runs = []
    for name, est in baseline_sequence(task, y["train"], seed, use_xgboost=use_xgboost).items():
        pipe = make_pipeline(pre, est).fit(X["train"], y["train"])
        definition = experiment_definition(h, split_def, seed, name, est.get_params())
        if task == "binary":
            p = {k: pipe.predict_proba(X[k])[:, 1] for k in ("val", "test")}
            thr, rule = choose_threshold(y["val"], p["val"], c.get("threshold_policy", "max_f1"),
                                         c.get("target_recall", 0.8))
            scores = {k: binary_metrics(y[k], p[k], thr) for k in ("val", "test")}
            definition["threshold_rule"] = rule
        elif task == "regression":
            scores = {k: regression_metrics(y[k], pipe.predict(X[k])) for k in ("val", "test")}
        else:
            scores = {k: multiclass_metrics(y[k], pipe.predict(X[k]), labels) for k in ("val", "test")}
        runs.append({**definition, "metrics": scores})
        log.info("%s %s val %s", definition["experiment_id"], name, c["primary_metric"])

    result = {"target": h.manifest["target"], "analyte": h.manifest.get("analyte"),
              "synthetic": bool(h.manifest.get("is_synthetic", False)), "primary_metric": c["primary_metric"],
              "split": split_def, "sizes": {k: len(v) for k, v in parts.items()}, "environment": run_environment(),
              "runs": runs}
    out = Path(out_dir) / f"{h.manifest['target']}-{runs[0]['dataset_sha256'][:12]}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "experiment.json").write_text(json.dumps(result, indent=2, default=str))
    return result
