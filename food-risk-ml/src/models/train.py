"""Experiment runner: split -> features -> baselines -> validation thresholds -> calibration -> SHAP -> registry."""

import importlib.metadata
import json
import logging
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import sklearn  # noqa: E402
from sklearn.metrics import precision_recall_curve  # noqa: E402

from src.config import ROOT  # noqa: E402
from src.data.contract import (  # noqa: E402
    ESTABLISHMENT_ID,
    TARGET,
    TASK,
    is_synthetic,
    validate_canonical,
)
from src.evaluation.calibration import PlattCalibrated, assess_calibration, reliability_plot  # noqa: E402
from src.evaluation.metrics import binary_metrics, choose_threshold, threshold_table  # noqa: E402
from src.explainability.shap_explain import Explainer, save_global_importance  # noqa: E402
from src.features.build import (  # noqa: E402
    HISTORY_FEATURES,
    build_daily_history,
    build_preprocessor,
    make_features,
    split_feature_types,
)
from src.features.leakage import assert_no_leaky_features  # noqa: E402
from src.features.split import make_split  # noqa: E402
from src.models.baselines import build_models, make_pipeline  # noqa: E402
from src.models.registry import save_model  # noqa: E402

log = logging.getLogger(__name__)
MEDIUM_BAND_RECALL = 0.95  # "medium" band = scores inside the validation 95%-recall net but below the threshold


def _version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def _git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _pr_plot(y: np.ndarray, probs: dict[str, np.ndarray], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 5))
    for name, p in probs.items():
        precision, recall, _ = precision_recall_curve(y, p)
        ax.plot(recall, precision, label=name)
    ax.axhline(y.mean(), ls="--", color="grey", label="prevalence")
    ax.set_xlabel("recall")
    ax.set_ylabel("precision")
    ax.set_title("Precision-recall (validation)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def select_model(val_pr_auc: dict[str, float], tie_tolerance: float, preference: list[str]) -> tuple[str, list[str]]:
    """Best validation PR-AUC; models within tie_tolerance of it are tied and the tie goes to `preference` order."""
    top = max(val_pr_auc.values())
    tied = [m for m, v in val_pr_auc.items() if v >= top - tie_tolerance]
    rank = {m: i for i, m in enumerate(preference)}
    return min(tied, key=lambda m: (rank.get(m, len(rank)), -val_pr_auc[m])), tied


def run_training(df: pd.DataFrame, cfg: dict, reports_dir: Path, registry_dir: Path, provenance: dict) -> dict:
    seed = cfg["seed"]
    np.random.seed(seed)
    reports_dir, registry_dir = Path(reports_dir), Path(registry_dir)
    (reports_dir / "thresholds").mkdir(parents=True, exist_ok=True)

    validate_canonical(df)
    synthetic = is_synthetic(df)
    if synthetic:
        log.warning("SYNTHETIC fixture data detected: outputs are code tests, not evaluation results")
    provenance = {**provenance, "synthetic": synthetic, "git_commit": _git_commit()}

    labelled = df[df[TARGET].notna()].copy()
    labelled[TARGET] = labelled[TARGET].astype(int)
    split = make_split(labelled, cfg, seed)
    prior_rate = float(split.train[TARGET].mean())
    # History needs trustworthy dates (strict time guard) and an establishment key.
    uses_history = split.method == "temporal" and bool(labelled[ESTABLISHMENT_ID].notna().any())
    # All labelled rows may serve as history: the time guard admits only results reported before each sample.
    daily = build_daily_history(labelled) if uses_history else None

    parts = split.parts()
    X = {k: make_features(v, daily, cfg, prior_rate) for k, v in parts.items()}
    y = {k: v[TARGET].to_numpy() for k, v in parts.items()}
    assert_no_leaky_features(list(X["train"].columns), allowed=HISTORY_FEATURES)
    cat, num = split_feature_types(X["train"])
    pre = build_preprocessor(cat, num, cfg["features"]["min_category_count"])
    t = cfg["threshold"]

    rows, fitted, p_val, p_test = [], {}, {}, {}
    for name, est in build_models(cfg, y["train"], seed).items():
        log.info("fitting %s", name)
        fitted[name] = make_pipeline(pre, est).fit(X["train"], y["train"])
        p_val[name] = fitted[name].predict_proba(X["val"])[:, 1]
        p_test[name] = fitted[name].predict_proba(X["test"])[:, 1]
        thr, _ = choose_threshold(y["val"], p_val[name], t["policy"], t["target_recall"])
        table = threshold_table(y["val"], p_val[name])  # thinned to <=500 evenly spaced rows for the report
        table.iloc[:: max(1, len(table) // 500)].to_csv(reports_dir / "thresholds" / f"{name}_val.csv", index=False)
        for s, p in (("val", p_val[name]), ("test", p_test[name])):
            rows.append({"model": name, "split": s, "synthetic": synthetic, **binary_metrics(y[s], p, thr)})
    metrics = pd.DataFrame(rows)
    metrics.to_csv(reports_dir / "metrics.csv", index=False)
    (reports_dir / "metrics.json").write_text(json.dumps(
        {"synthetic": synthetic, "split": split.method, "split_notes": split.notes, "rows": rows}, indent=2))
    _pr_plot(y["val"], p_val, reports_dir / "pr_curves_val.png")

    # Model selection uses validation PR-AUC only; the test split is reported, never used to choose.
    cand = metrics[(metrics["split"] == "val") & (metrics["model"] != "dummy_prior")]
    sel = cfg["selection"]
    best, tied = select_model(dict(zip(cand["model"], cand["pr_auc"], strict=True)), sel["tie_tolerance"],
                              sel["preference"])
    log.info("selected %s (tied within %.3f validation PR-AUC: %s)", best, sel["tie_tolerance"], tied)
    pipe = fitted[best]
    cal = assess_calibration(y["val"], p_val[best], seed)
    final = PlattCalibrated(pipe).fit(p_val[best], y["val"]) if cal["apply"] else pipe
    fv, ft = final.predict_proba(X["val"])[:, 1], final.predict_proba(X["test"])[:, 1]
    thr, how = choose_threshold(y["val"], fv, t["policy"], t["target_recall"])
    medium_from = min(choose_threshold(y["val"], fv, "min_recall", MEDIUM_BAND_RECALL)[0], thr)
    curves = {"raw": p_test[best], "platt": ft} if cal["apply"] else {"raw": p_test[best]}
    reliability_plot(y["test"], curves, reports_dir / "calibration_test.png", f"Reliability ({best}, test)")

    background = X["train"].sample(min(200, len(X["train"])), random_state=seed)
    explainer = Explainer(pipe, background)
    importance = None
    if explainer.supported:
        sample = X["test"].sample(min(cfg["explain"]["shap_sample"], len(X["test"])), random_state=seed)
        importance = save_global_importance(explainer.global_importance(sample), reports_dir, explainer.units)

    version = f"{cfg['pathogen'].lower()}-{best}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    final_report = {
        "model_version": version, "selected_model": best,
        "selection": f"max validation PR-AUC (dummy excluded); models within {sel['tie_tolerance']} tied, "
                     f"tie goes to preference order {sel['preference']}",
        "tied_models": tied,
        "calibration": cal, "threshold": thr, "threshold_rule": how,
        "val": binary_metrics(y["val"], fv, thr), "test": binary_metrics(y["test"], ft, thr),
    }
    metadata = {
        "model_version": version, "task": TASK, "pathogen": cfg["pathogen"],
        "target": f"{TARGET}: laboratory sample tested positive for {cfg['pathogen']} (not batch safety)",
        "created_at": datetime.now(UTC).isoformat(), "provenance": provenance,
        "split": {"method": split.method, "notes": split.notes,
                  "sizes": {k: len(v) for k, v in parts.items()}},
        "features": {"all": list(X["train"].columns), "categorical": cat, "numeric": num,
                     "uses_history": uses_history, "prior_rate": prior_rate,
                     "history_params": {k: cfg["features"][k] for k in ("label_lag_days", "history_smoothing")}},
        "threshold": thr, "threshold_rule": how,
        "risk_bands": {"high_from": thr, "medium_from": medium_from,
                       "definition": f"high: score >= operating threshold; medium: within validation "
                                     f"{MEDIUM_BAND_RECALL:.0%}-recall net; low: below. Low does not mean safe."},
        "calibration": cal, "imbalance_strategy": cfg["imbalance"]["strategy"], "explain_top_k": cfg["explain"]["top_k"],
        "metrics": {"val": final_report["val"], "test": final_report["test"]},
        "versions": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                     "xgboost": _version("xgboost"), "shap": _version("shap"), "pandas": pd.__version__},
        "config": cfg,
    }
    model_dir = save_model(registry_dir, final, metadata, daily, background)
    final_report["model_dir"] = str(model_dir)
    final_report["synthetic"] = synthetic
    final_report["top_features"] = importance.head(10).to_dict("records") if importance is not None else None
    (reports_dir / "final_model.json").write_text(json.dumps(final_report, indent=2, default=str))
    return final_report
