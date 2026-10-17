"""Probability calibration: assess, and apply Platt scaling only when it helps out-of-fold on validation."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.calibration import calibration_curve  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import brier_score_loss  # noqa: E402
from sklearn.model_selection import StratifiedKFold  # noqa: E402

EPS = 1e-6


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p)).reshape(-1, 1)


class PlattCalibrated:
    """A fitted pipeline plus a monotonic sigmoid map of its scores. Ranking (and thus PR/ROC AUC) is
    unchanged; only the probability scale moves. `pipeline` stays exposed for explanations."""

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.calibrator = LogisticRegression(C=1e6)

    def fit(self, p_raw: np.ndarray, y: np.ndarray) -> "PlattCalibrated":
        self.calibrator.fit(_logit(p_raw), y)
        return self

    def predict_proba(self, X) -> np.ndarray:
        p = self.calibrator.predict_proba(_logit(self.pipeline.predict_proba(X)[:, 1]))[:, 1]
        return np.column_stack([1 - p, p])


def assess_calibration(y_val: np.ndarray, p_val: np.ndarray, seed: int, folds: int = 5) -> dict:
    """Compare raw validation Brier with out-of-fold Platt-calibrated Brier on the validation set."""
    y_val = np.asarray(y_val).astype(int)
    folds = min(folds, int(np.bincount(y_val).min()))
    if folds < 2:
        return {"raw_brier": float(brier_score_loss(y_val, p_val)), "platt_oof_brier": None, "apply": False,
                "reason": "too few positives in validation to assess calibration"}
    oof = np.zeros(len(y_val))
    for tr, te in StratifiedKFold(folds, shuffle=True, random_state=seed).split(p_val.reshape(-1, 1), y_val):
        oof[te] = LogisticRegression(C=1e6).fit(_logit(p_val[tr]), y_val[tr]).predict_proba(_logit(p_val[te]))[:, 1]
    raw, cal = float(brier_score_loss(y_val, p_val)), float(brier_score_loss(y_val, oof))
    return {"raw_brier": raw, "platt_oof_brier": cal, "apply": cal < raw,
            "reason": "Platt scaling lowers out-of-fold validation Brier" if cal < raw
            else "raw probabilities already at least as well calibrated"}


def reliability_plot(y: np.ndarray, curves: dict[str, np.ndarray], path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "--", color="grey", label="perfect")
    for name, p in curves.items():
        frac, mean = calibration_curve(y, p, n_bins=10, strategy="quantile")
        ax.plot(mean, frac, marker="o", label=name)
    ax.set_xlabel("mean predicted probability")
    ax.set_ylabel("observed positive fraction")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
