"""Classification metrics and validation-only threshold selection."""

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, precision_recall_curve, roc_auc_score


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
