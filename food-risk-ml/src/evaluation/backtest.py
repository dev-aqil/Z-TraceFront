"""Rolling-origin backtest for the FSIS pipeline: the honest way to compare features and models.

Every row on or after `sealed_test_start` is sealed: never trained on, never used as history, never scored here.
Each fold trains on all development rows before its window and scores the window (e.g. one fiscal year), so
improvements are judged across several later periods instead of one validation slice. Ranking metrics only
(PR-AUC, ROC-AUC, recall at an inspection budget) with bootstrap CIs; thresholds and calibration are chosen
later, once, on the final model.
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from src.data.contract import PRODUCT_CATEGORY, SAMPLE_DATE, TARGET, is_synthetic, validate_canonical
from src.evaluation.metrics import bootstrap_ci, recall_at_budget
from src.features.build import (
    HISTORY_FEATURES,
    build_daily_history,
    build_preprocessor,
    make_features,
    split_feature_types,
)
from src.features.leakage import assert_no_leaky_features
from src.models.baselines import build_models, make_pipeline

log = logging.getLogger(__name__)


def fold_windows(starts: list[str], months: int, sealed_from: pd.Timestamp) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    windows = []
    for s in starts:
        start = pd.Timestamp(s)
        end = min(start + pd.DateOffset(months=months), sealed_from)
        if start >= sealed_from:
            raise ValueError(f"fold starting {s} is inside the sealed test period")
        windows.append((start, end))
    return windows


def _score(y: np.ndarray, p: np.ndarray, budgets: list[float], n_boot: int, seed: int) -> dict:
    out = {"n": len(y), "prevalence": float(y.mean()), "pr_auc": float(average_precision_score(y, p)),
           "pr_auc_ci": bootstrap_ci(average_precision_score, y, p, n_boot, seed),
           "roc_auc": float(roc_auc_score(y, p))}
    for b in budgets:
        r = recall_at_budget(y, p, b)
        out[f"recall_at_{int(b * 100)}pct"] = r["recall"]
        out[f"recall_at_{int(b * 100)}pct_ci"] = bootstrap_ci(lambda yy, pp, b=b: recall_at_budget(yy, pp, b)["recall"],
                                                             y, p, n_boot, seed)
    return out


def run_backtest(df: pd.DataFrame, cfg: dict, out_dir: Path, label: str = "baseline",
                 models: list[str] | None = None) -> dict:
    bt, seed = cfg["backtest"], cfg["seed"]
    validate_canonical(df)
    labelled = df[df[TARGET].notna()].copy()
    labelled[TARGET] = labelled[TARGET].astype(int)
    sealed_from = pd.Timestamp(bt["sealed_test_start"])
    dev = labelled[labelled[SAMPLE_DATE] < sealed_from]  # sealed rows never enter, not even as history
    daily = build_daily_history(dev)

    folds, rows = [], []
    for start, end in fold_windows(bt["fold_starts"], bt["fold_months"], sealed_from):
        train = dev[dev[SAMPLE_DATE] < start]
        ev = dev[(dev[SAMPLE_DATE] >= start) & (dev[SAMPLE_DATE] < end)]
        if train[TARGET].nunique() < 2 or ev[TARGET].nunique() < 2:
            raise ValueError(f"fold {start.date()}: a class is missing in train or evaluation")
        prior = float(train[TARGET].mean())
        X_tr, X_ev = make_features(train, daily, cfg, prior), make_features(ev, daily, cfg, prior)
        assert_no_leaky_features(list(X_tr.columns), allowed=HISTORY_FEATURES)
        cat, num = split_feature_types(X_tr)
        pre = build_preprocessor(cat, num, cfg["features"]["min_category_count"])
        y_tr, y_ev = train[TARGET].to_numpy(), ev[TARGET].to_numpy()
        fold = f"{start.date()}..{(end - pd.Timedelta(days=1)).date()}"
        for name, est in build_models(cfg, y_tr, seed).items():
            if models and name not in models:
                continue
            log.info("fold %s: fitting %s on %d rows", fold, name, len(train))
            p = make_pipeline(pre, est).fit(X_tr, y_tr).predict_proba(X_ev)[:, 1]
            score = _score(y_ev, p, bt["budgets"], bt["bootstrap"], seed)
            by_prog = {}
            for prog, idx in ev.groupby(PRODUCT_CATEGORY).indices.items():
                yy = y_ev[idx]
                if len(yy) >= bt["min_programme_rows"] and 0 < yy.sum() < len(yy):
                    by_prog[prog] = {"n": len(yy), "prevalence": float(yy.mean()),
                                     "pr_auc": float(average_precision_score(yy, p[idx]))}
            rows.append({"fold": fold, "model": name, "train_rows": len(train), **score, "by_programme": by_prog})
        folds.append(fold)

    table = pd.DataFrame(rows)
    summary = (table.groupby("model")[["pr_auc", "roc_auc"] + [c for c in table if c.startswith("recall_at_")
                                                                and not c.endswith("_ci")]]
               .agg(["mean", "min"]).round(4))
    summary.columns = ["_".join(c) for c in summary.columns]
    result = {"label": label, "synthetic": is_synthetic(df), "sealed_test_start": str(sealed_from.date()),
              "folds": folds, "summary": summary.reset_index().to_dict("records"), "runs": rows}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"backtest_{label}.json").write_text(json.dumps(result, indent=2, default=str))
    table.drop(columns="by_programme").to_csv(out / f"backtest_{label}.csv", index=False)
    return result
