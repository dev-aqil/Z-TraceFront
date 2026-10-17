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
from sklearn.metrics import average_precision_score, precision_recall_curve  # noqa: E402

from src.config import ROOT  # noqa: E402
from src.data.contract import (  # noqa: E402
    ESTABLISHMENT_ID,
    TARGET,
    TASK,
    is_synthetic,
    validate_canonical,
)
from src.evaluation.calibration import PlattCalibrated, assess_calibration, reliability_plot  # noqa: E402
from src.evaluation.metrics import binary_metrics, choose_threshold, paired_bootstrap_diff, threshold_table  # noqa: E402
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
SELECTION_RULE = ("max validation PR-AUC among learned models, unless statistically tied (paired-bootstrap 95% CI "
                  "of leader minus model includes 0); a tie goes to the preference order")
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


def select_model(y_val: np.ndarray, p_val: dict[str, np.ndarray], preference: list[str], n_boot: int,
                 seed: int) -> tuple[str, list[str], dict]:
    """Best validation PR-AUC, unless the data cannot tell it apart from another model: a model is tied with the
    leader when the paired-bootstrap 95% interval of (leader - model) PR-AUC includes 0. Ties go to `preference`
    order (cheapest to explain per request and on s390x). Scales with how many positives validation has, unlike a
    fixed tolerance, which is meaningless for rare targets."""
    scores = {m: float(average_precision_score(y_val, p)) for m, p in p_val.items()}
    leader = max(scores, key=scores.get)
    tests = {m: paired_bootstrap_diff(average_precision_score, y_val, p_val[leader], p, n_boot, seed)
             for m, p in p_val.items() if m != leader}
    tied = [leader] + [m for m, r in tests.items() if r["ci"][0] <= 0]
    rank = {m: i for i, m in enumerate(preference)}
    return min(tied, key=lambda m: (rank.get(m, len(rank)), -scores[m])), tied, {"leader": leader, "vs_leader": tests}


def run_training(df: pd.DataFrame, cfg: dict, reports_dir: Path, registry_dir: Path, provenance: dict,
                 pinned_model: str | None = None) -> dict:
    """pinned_model: retrain a model type already chosen on the reference platform instead of re-selecting.
    Used on s390x, where older library versions can move a borderline tie test (beef STEC, 2026-10-17)."""
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
    sel = cfg["selection"]
    best, tied, tie_tests = select_model(y["val"], {m: p for m, p in p_val.items() if m != "dummy_prior"},
                                         sel["preference"], sel["bootstrap"], seed)
    if pinned_model:
        if pinned_model not in fitted or pinned_model == "dummy_prior":
            raise ValueError(f"pinned model {pinned_model!r} is not a candidate: {sorted(fitted)}")
        log.info("PINNED %s (this platform's own selection would be %s, tied: %s)", pinned_model, best, tied)
        tie_tests["platform_selection"], best = best, pinned_model
    log.info("selected %s (statistically tied on validation PR-AUC: %s)", best, tied)
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

    version = f"{cfg['pathogen_key']}-{best}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    final_report = {
        "model_version": version, "selected_model": best,
        "selection": f"{SELECTION_RULE}; preference {sel['preference']}",
        "tied_models": tied, "tie_tests": tie_tests, "pinned_model": pinned_model,
        "calibration": cal, "threshold": thr, "threshold_rule": how,
        "val": binary_metrics(y["val"], fv, thr), "test": binary_metrics(y["test"], ft, thr),
    }
    metadata = {
        "model_version": version, "task": TASK, "pathogen": cfg["pathogen"], "product": cfg["product"],
        "model_key": cfg["pathogen_key"], "selection": {"rule": SELECTION_RULE, "tied": tied, "pinned_model": pinned_model},
        "target": f"{TARGET}: laboratory sample tested positive for {cfg['pathogen']} (not batch safety)",
        "created_at": datetime.now(UTC).isoformat(), "provenance": provenance,
        "split": {"method": split.method, "notes": split.notes,
                  "sizes": {k: len(v) for k, v in parts.items()}},
        "features": {"all": list(X["train"].columns), "categorical": cat, "numeric": num,
                     "uses_history": uses_history, "prior_rate": prior_rate,
                     "normalise_text": bool((provenance.get("upstream") or {}).get("normalise_text", False)),
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
