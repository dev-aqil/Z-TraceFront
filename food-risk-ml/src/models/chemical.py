"""Chemical detection model from Person A's PDP handoff: readiness gate -> audited split -> baselines incl. a
commodity-rate baseline -> calibration -> SHAP -> registry.

Person A ships a readiness bundle (readiness.json pinning the dataset, feature manifest and leakage audit by
SHA-256). `load_pdp_readiness` checks every pin, rejects undeclared columns, translates the bundle into this
package's handoff format and passes it through the same gate as every target (`contracts.gate`).

Feature availability: Person A's features are native sample descriptors (commodity, form, origin, country, claim,
unit count) and the collection weekday, fixed when the sample is collected. Person A proves only release-time
public availability, which is why the target's scope is RETROSPECTIVE_RELEASE_COHORT_ONLY.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.metrics import average_precision_score

from src.data.contract import SYNTHETIC_ID_PREFIX
from src.evaluation.calibration import PlattCalibrated, assess_calibration, reliability_plot
from src.evaluation.metrics import (
    binary_metrics,
    bootstrap_ci,
    choose_threshold,
    paired_bootstrap_diff,
    recall_at_budget,
)
from src.explainability.shap_explain import Explainer, save_global_importance
from src.features.build import build_preprocessor
from src.models.baselines import build_models, make_pipeline
from src.models.contracts import (
    ContractError,
    Handoff,
    NotModelReadyError,
    gate,
    load_targets,
    sha256_file,
)
from src.models.experiment import feature_matrix
from src.models.registry import save_model
from src.models.train import MEDIUM_BAND_RECALL, _git_commit, _version, select_model

log = logging.getLogger(__name__)
PINS = {"dataset_path": "dataset_sha256", "feature_manifest_path": "feature_manifest_sha256",
        "leakage_audit_path": "leakage_audit_sha256"}
PARTS = {"train": "train", "val": "validation", "test": "test"}  # ours -> Person A's split_audit names
COMMODITY = "pdp_commodity_code"


def load_pdp_readiness(readiness_path: str | Path, targets: dict | None = None) -> tuple[Handoff, dict]:
    """Returns the gated handoff and Person A's split audit. Raises NotModelReadyError / ContractError."""
    p = Path(readiness_path).resolve()
    if not p.exists():
        raise NotModelReadyError(f"no readiness file at {p}")
    r = json.loads(p.read_text(encoding="utf-8"))
    if r.get("model_ready") is not True or r.get("leakage_audit_passed") is not True:
        raise NotModelReadyError(f"{p.name}: model_ready={r.get('model_ready')!r}, "
                                 f"leakage_audit_passed={r.get('leakage_audit_passed')!r}")
    root = next((c for c in p.parents if (c / r["dataset_path"]).is_file()), None)
    if root is None:
        raise NotModelReadyError(f"dataset {r['dataset_path']} not found above {p.parent}")
    for path_key, sha_key in PINS.items():
        actual = sha256_file(root / r[path_key])
        if actual != r[sha_key]:
            raise NotModelReadyError(f"{r[path_key]}: sha256 {actual} does not match readiness {r[sha_key]}")
    fm = json.loads((root / r["feature_manifest_path"]).read_text(encoding="utf-8"))
    audit = json.loads((root / r["leakage_audit_path"]).read_text(encoding="utf-8"))["split_audit"]

    targets = targets or load_targets()
    contract = targets["targets"].get(r["target"], {})
    excluded = set(contract.get("excluded_features", []))
    table_path = root / r["dataset_path"]
    head = pd.read_csv(table_path, dtype=str, nrows=0).columns
    declared = set(fm["FEATURES"]) | set(fm["IDENTIFIER_ONLY"]) | set(fm["METADATA_ONLY"]) | {fm["TARGET"]}
    if set(head) - declared:  # Person A's contract: unknown columns REJECT
        raise ContractError(f"undeclared columns in {table_path.name}: {sorted(set(head) - declared)}")
    if leaked := set(fm["FEATURES"]) & set(fm["FORBIDDEN"]):
        raise ContractError(f"feature manifest lists forbidden columns as features: {sorted(leaked)}")
    analytes = pd.read_csv(table_path, dtype=str, usecols=["analyte_code"])["analyte_code"].unique()
    if len(analytes) != 1:
        raise ContractError(f"one model per analyte; table has {sorted(analytes)}")

    m = {
        "model_ready": True, "target": r["target"], "target_column": fm["TARGET"],
        "analyte": f"PDP analyte {analytes[0]}", "dataset_id": r["dataset"], "dataset_version": r["version"],
        "prediction_time_column": r["time_column"], "id_columns": fm["IDENTIFIER_ONLY"],
        "group_columns": {"sample": r["group_column"]},
        "table": {"path": str(table_path), "sha256": r["dataset_sha256"], "null_token": fm["null_encoding"],
                  "row_count": r["rows"]},
        "features": [{"name": n, "dtype": "numeric" if n in fm["numeric_features"] else "categorical",
                      "availability": "pre_prediction"} for n in fm["FEATURES"] if n not in excluded],
        "excluded_by_contract": [n for n in fm["FEATURES"] if n in excluded],
        "readiness": {k: r[k] for k in ("readiness_scope", "prospective_deployment_ready", "observation_time",
                                        *PINS.values(), "schema_sha256", "provenance_sha256")},
    }
    return gate(m, root, targets), audit


def audited_split(h: Handoff, audit: dict) -> dict[str, pd.DataFrame]:
    """Person A's whole-day boundaries, re-applied and checked against the audited counts."""
    t = h.table[h.manifest["prediction_time_column"]].dt.tz_convert(None).dt.normalize()
    parts = {}
    for ours, theirs in PARTS.items():
        a = audit["partitions"][theirs]
        part = h.table[(t >= pd.Timestamp(a["min_date"])) & (t <= pd.Timestamp(a["max_date"]))]
        counts = {str(k): int(v) for k, v in part[h.target].value_counts().items()}
        if len(part) != a["rows"] or counts != {k: int(v) for k, v in a["target_counts"].items()}:
            raise ContractError(f"{ours}: {len(part)} rows {counts} differ from Person A's audit {a}")
        parts[ours] = part.reset_index(drop=True)
    if sum(len(v) for v in parts.values()) != len(h.table):
        raise ContractError("audited partitions do not cover every labelled row")
    return parts


class CommodityRate:
    """Baseline: each commodity's training detection rate, smoothed toward the overall rate with `k` pseudo-samples.
    If the learned model cannot beat this, commodity alone explains what it learned."""

    def __init__(self, k: float):
        self.k = k

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "CommodityRate":
        self.prior_ = float(np.mean(y))
        g = pd.DataFrame({"c": X[COMMODITY].to_numpy(), "y": y}).groupby("c")["y"].agg(["sum", "size"])
        self.rates_ = ((g["sum"] + self.k * self.prior_) / (g["size"] + self.k)).to_dict()
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        p = X[COMMODITY].map(self.rates_).fillna(self.prior_).to_numpy(dtype=float)
        return np.column_stack([1 - p, p])


def run_chemical(cfg: dict, key: str = "imidacloprid", readiness: str | Path | None = None,
                 reports_dir: Path | None = None, registry_dir: Path | None = None) -> dict:
    from src.config import resolve
    c = cfg["chemical"][key]
    seed, n_boot = cfg["seed"], c["bootstrap"]
    reports_dir = Path(reports_dir or resolve(c["reports"]))
    registry_dir = Path(registry_dir or resolve(c["registry"]))
    reports_dir.mkdir(parents=True, exist_ok=True)

    h, audit = load_pdp_readiness(readiness or resolve(c["readiness"]))
    synthetic = bool(h.table[h.manifest["group_columns"]["sample"]].astype(str).str.startswith(SYNTHETIC_ID_PREFIX).any())
    parts = audited_split(h, audit)
    X = {k: feature_matrix(h, v) for k, v in parts.items()}
    y = {k: v[h.target].to_numpy() for k, v in parts.items()}
    cat, num = h.features("categorical"), h.features("numeric")
    pre = build_preprocessor(cat, num, cfg["features"]["min_category_count"])
    t, sel = h.contract, cfg["selection"]

    fitted, p = {}, {}
    candidates = {"commodity_rate": CommodityRate(cfg["features"]["history_smoothing"])}
    candidates |= {n: make_pipeline(pre, est) for n, est in build_models(cfg, y["train"], seed).items()}
    rows = []
    for name, model in candidates.items():
        log.info("fitting %s", name)
        fitted[name] = model.fit(X["train"], y["train"])
        p[name] = {k: fitted[name].predict_proba(X[k])[:, 1] for k in ("val", "test")}
        thr, _ = choose_threshold(y["val"], p[name]["val"], t["threshold_policy"], t["target_recall"])
        for s in ("val", "test"):
            rows.append({"model": name, "split": s, "synthetic": synthetic, **binary_metrics(y[s], p[name][s], thr),
                         "pr_auc_ci": bootstrap_ci(average_precision_score, y[s], p[name][s], n_boot, seed),
                         **{f"recall_at_{int(b * 100)}pct": recall_at_budget(y[s], p[name][s], b)["recall"]
                            for b in cfg["backtest"]["budgets"]}})
    metrics = pd.DataFrame(rows)
    metrics.to_csv(reports_dir / "metrics.csv", index=False)

    # Selection: validation PR-AUC among learned models, same tie rule as the pathogen models.
    learned = metrics[(metrics["split"] == "val") & ~metrics["model"].isin(["dummy_prior", "commodity_rate"])]
    best, tied = select_model(dict(zip(learned["model"], learned["pr_auc"], strict=True)), sel["tie_tolerance"],
                              sel["preference"])
    log.info("selected %s (tied within %.3f validation PR-AUC: %s)", best, sel["tie_tolerance"], tied)
    # The pre-registered question: does the model add anything beyond commodity? Paired, same resamples.
    vs_commodity = {s: paired_bootstrap_diff(average_precision_score, y[s], p[best][s], p["commodity_rate"][s],
                                             n_boot, seed) for s in ("val", "test")}

    pipe = fitted[best]
    cal = assess_calibration(y["val"], p[best]["val"], seed)
    final = PlattCalibrated(pipe).fit(p[best]["val"], y["val"]) if cal["apply"] else pipe
    fv, ft = final.predict_proba(X["val"])[:, 1], final.predict_proba(X["test"])[:, 1]
    thr, how = choose_threshold(y["val"], fv, t["threshold_policy"], t["target_recall"])
    medium_from = min(choose_threshold(y["val"], fv, "min_recall", MEDIUM_BAND_RECALL)[0], thr)
    reliability_plot(y["test"], {"raw": p[best]["test"], **({"platt": ft} if cal["apply"] else {})},
                     reports_dir / "calibration_test.png", f"Reliability ({best}, test)")

    # Ablation only (decided before training): restore the calendar features the contract excludes.
    ablation = None
    if excl := h.manifest["excluded_by_contract"]:
        Xa = {k: X[k].assign(**{e: pd.to_numeric(parts[k][e]) for e in excl}) for k in X}
        pa = make_pipeline(build_preprocessor(cat, num + excl, cfg["features"]["min_category_count"]),
                           clone(pipe.named_steps["model"])).fit(Xa["train"], y["train"])
        ablation = {"added_features": excl, "model": best, **{
            s: {"pr_auc": float(average_precision_score(y[s], q := pa.predict_proba(Xa[s])[:, 1])),
                "pr_auc_ci": bootstrap_ci(average_precision_score, y[s], q, n_boot, seed)} for s in ("val", "test")}}

    background = X["train"].sample(min(200, len(X["train"])), random_state=seed)
    explainer, importance = Explainer(pipe, background), None
    if explainer.supported:
        importance = save_global_importance(explainer.global_importance(X["test"]), reports_dir, explainer.units)

    version = f"chemical-{key}-{best}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    summary = {
        "model_version": version, "selected_model": best, "tied_models": tied,
        "selection": f"max validation PR-AUC among learned models; within {sel['tie_tolerance']} tied, "
                     f"preference {sel['preference']}",
        "calibration": cal, "threshold": thr, "threshold_rule": how,
        "val": binary_metrics(y["val"], fv, thr), "test": binary_metrics(y["test"], ft, thr),
        "test_pr_auc_ci": bootstrap_ci(average_precision_score, y["test"], ft, n_boot, seed),
        "test_recall_at_budget": {f"{int(b * 100)}pct": recall_at_budget(y["test"], ft, b)
                                  for b in cfg["backtest"]["budgets"]},
        "vs_commodity_rate_pr_auc": vs_commodity, "ablation_with_calendar_position": ablation,
        "sizes": {k: len(v) for k, v in parts.items()}, "synthetic": synthetic,
        "top_features": importance.head(10).to_dict("records") if importance is not None else None,
    }
    metadata: dict[str, Any] = {
        "model_version": version, "task": f"chemical_{h.target}", "domain": "CHEMICAL", "target": h.target,
        "analyte": h.manifest["analyte"], "scope": t["scope"],
        "target_meaning": t["positive_meaning"], "created_at": datetime.now(UTC).isoformat(),
        "provenance": {"synthetic": synthetic, "git_commit": _git_commit(), "dataset_id": h.manifest["dataset_id"],
                       "dataset_version": h.manifest["dataset_version"], **h.manifest["readiness"]},
        "split": {"method": "person_a_audited_temporal", "audit": audit, "sizes": summary["sizes"]},
        "features": {"all": cat + num, "categorical": cat, "numeric": num,
                     "excluded_by_contract": h.manifest["excluded_by_contract"]},
        "threshold": thr, "threshold_rule": how,
        "risk_bands": {"high_from": thr, "medium_from": medium_from,
                       "definition": "high: score >= operating threshold; medium: within validation "
                                     f"{MEDIUM_BAND_RECALL:.0%}-recall net; low: below. Low does not mean no residue."},
        "calibration": cal, "explain_top_k": cfg["explain"]["top_k"],
        "metrics": {"val": summary["val"], "test": summary["test"]},
        "versions": {"sklearn": sklearn.__version__, "xgboost": _version("xgboost"), "shap": _version("shap"),
                     "pandas": pd.__version__},
    }
    summary["model_dir"] = str(save_model(registry_dir, final, metadata, None, background))
    (reports_dir / "final_model.json").write_text(json.dumps(summary, indent=2, default=str))
    return summary
