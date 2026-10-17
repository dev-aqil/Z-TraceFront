"""Classification and regression metrics, and validation-only threshold selection."""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_recall_curve,
    r2_score,
    recall_score,
    roc_auc_score,
)


def recall_at_budget(y: np.ndarray, p: np.ndarray, budget: float) -> dict:
    """If inspectors can only test the top `budget` share of samples ranked by score, what share of all positives
    do they catch, and how precise is that set? Samples tied with the cut-off score are taken proportionally
    (expected value of a random tie-break), so row order never changes the result."""
    y, p = np.asarray(y).astype(int), np.asarray(p, dtype=float)
    k = max(1, int(round(budget * len(y))))
    cut = np.sort(p)[::-1][k - 1]
    above, tied = p > cut, p == cut
    caught = y[above].sum() + y[tied].sum() * (k - above.sum()) / tied.sum()
    return {"budget": budget, "recall": caught / y.sum() if y.sum() else None, "precision": caught / k,
            "lift": (caught / y.sum()) / budget if y.sum() else None}


def bootstrap_ci(metric, y: np.ndarray, p: np.ndarray, n: int = 200, seed: int = 0,
                 level: float = 0.95) -> tuple[float, float]:
    """Percentile bootstrap CI of metric(y, p) over resampled rows. Resamples lacking a class are skipped."""
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y), np.asarray(p)
    vals = []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) == 2:
            vals.append(metric(y[idx], p[idx]))
    a = (1 - level) / 2
    return float(np.quantile(vals, a)), float(np.quantile(vals, 1 - a))


def regression_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    """MAE/RMSE in target units, R^2, and a residual summary (bias and spread) for residual analysis."""
    y, pred = np.asarray(y, dtype=float), np.asarray(pred, dtype=float)
    resid = y - pred
    return {
        "n": len(y), "mae": float(mean_absolute_error(y, pred)), "rmse": float(np.sqrt(np.mean(resid ** 2))),
        "r2": float(r2_score(y, pred)) if len(y) > 1 and np.var(y) > 0 else None,
        "residual_mean": float(resid.mean()), "residual_p05": float(np.percentile(resid, 5)),
        "residual_p95": float(np.percentile(resid, 95)),
    }


def multiclass_metrics(y: np.ndarray, pred: np.ndarray, labels: list) -> dict:
    """Macro-F1 and per-class recall: a missed spoiled class matters regardless of its frequency."""
    return {
        "n": len(y), "macro_f1": float(f1_score(y, pred, labels=labels, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "per_class_recall": dict(zip(map(str, labels), map(float, recall_score(y, pred, labels=labels, average=None,
                                                                              zero_division=0)), strict=True)),
        "confusion_matrix": confusion_matrix(y, pred, labels=labels).tolist(), "labels": [str(x) for x in labels],
    }


def binary_metrics(y: np.ndarray, p: np.ndarray, threshold: float) -> dict:
    y = np.asarray(y).astype(int)
    pred = (np.asarray(p) >= threshold).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())

    def ratio(a: int, b: int) -> float | None:
        return a / b if b else None

    precision, recall = ratio(tp, tp + fp), ratio(tp, tp + fn)
    both = len(np.unique(y)) == 2
    return {
        "n": len(y), "prevalence": float(y.mean()), "threshold": float(threshold),
        "precision": precision, "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision and recall else 0.0,
        "specificity": ratio(tn, tn + fp), "false_negative_rate": ratio(fn, fn + tp),
        "pr_auc": float(average_precision_score(y, p)) if both else None,
        "roc_auc": float(roc_auc_score(y, p)) if both else None,
        "brier": float(brier_score_loss(y, p)),
        "tn": tn, "fp": fp, "fn": fn, "tp": tp,
    }


def threshold_table(y: np.ndarray, p: np.ndarray) -> pd.DataFrame:
    """Precision/recall/F1 at every candidate threshold (validation trade-off curve)."""
    precision, recall, thr = precision_recall_curve(y, p)
    precision, recall = precision[:-1], recall[:-1]
    f1 = np.divide(2 * precision * recall, precision + recall, out=np.zeros_like(precision),
                   where=(precision + recall) > 0)
    return pd.DataFrame({"threshold": thr, "precision": precision, "recall": recall, "f1": f1})


def choose_threshold(y: np.ndarray, p: np.ndarray, policy: str, target_recall: float) -> tuple[float, str]:
    """Pick a threshold from validation data only. Returns (threshold, description)."""
    t = threshold_table(y, p)
    if policy == "min_recall":
        ok = t[t["recall"] >= target_recall]
        if len(ok):
            best = ok.sort_values(["precision", "threshold"], ascending=False).iloc[0]
            return float(best["threshold"]), f"highest-precision threshold with validation recall >= {target_recall}"
        policy = "max_f1"
    if policy == "max_f1":
        best = t.sort_values(["f1", "threshold"], ascending=False).iloc[0]
        return float(best["threshold"]), "threshold maximising validation F1"
    raise ValueError(f"unknown threshold policy {policy!r}")
