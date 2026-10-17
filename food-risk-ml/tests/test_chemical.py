"""Chemical handoff adapter and training, on a SYNTHETIC readiness bundle (invented codes; not PDP data)."""

import copy
import json

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score

from src.evaluation.metrics import paired_bootstrap_diff
from src.models.chemical import CommodityRate, audited_split, load_pdp_readiness, run_chemical
from src.models.contracts import ContractError, NotModelReadyError, sha256_file

FEATURES = ["pdp_commodity_code", "pdp_commodity_type_code", "pdp_origin_code", "pdp_import_origin_country_code",
            "pdp_product_claim_code", "pdp_sample_unit_count", "pdp_collection_dow_iso", "pdp_collection_doy",
            "pdp_collection_isoweek"]
NUMERIC = ["pdp_sample_unit_count", "pdp_collection_dow_iso", "pdp_collection_doy", "pdp_collection_isoweek"]
IDS = ["observation_id", "pdp_sample_id", "pdp_source_row_number", "pdp_result_source_row_number"]
META = ["collection_date", "observation_time", "source_release", "analyte_code"]
CUTS = {"train": ("2024-01-02", "2024-08-31"), "validation": ("2024-09-01", "2024-10-31"),
        "test": ("2024-11-01", "2024-12-23")}


def write_bundle(root, n=1500, seed=0, extra_column=None, model_ready=True):
    rng = np.random.default_rng(seed)
    dates = pd.Timestamp("2024-01-02") + pd.to_timedelta(np.sort(rng.integers(0, 356, n)), unit="D")
    comm = rng.choice(["SA", "SB", "SC", "SD"], n)
    y = rng.binomial(1, pd.Series(comm).map({"SA": 0.15, "SB": 0.06, "SC": 0.01, "SD": 0.0}).to_numpy())
    t = pd.DataFrame({
        "observation_id": [f"obs{i}" for i in range(n)], "pdp_sample_id": [f"SYNTH-{i:05d}" for i in range(n)],
        "pdp_source_row_number": [str(i) for i in range(n)], "pdp_result_source_row_number": [str(i) for i in range(n)],
        "collection_date": dates.strftime("%Y-%m-%d"), "observation_time": "2025-12-24", "source_release": "SYNTH",
        "analyte_code": "000", "pdp_commodity_code": comm, "pdp_commodity_type_code": rng.choice(["F1", "F2"], n),
        "pdp_origin_code": rng.choice(["1", "2"], n), "pdp_import_origin_country_code": rng.choice(["\\N", "C1"], n),
        "pdp_product_claim_code": "NC", "pdp_sample_unit_count": rng.choice(["\\N", "1", "4"], n),
        "pdp_collection_dow_iso": [str(d.isoweekday()) for d in dates], "pdp_collection_doy": dates.dayofyear.astype(str),
        "pdp_collection_isoweek": [str(d.isocalendar().week) for d in dates], "imidacloprid_detected": y.astype(str),
    })
    if extra_column:
        t[extra_column] = "x"
    (root / "data" / "processed").mkdir(parents=True)
    (root / "reports").mkdir()
    csv = root / "data/processed/synth.csv"
    t.to_csv(csv, index=False)
    fm = {"FEATURES": FEATURES, "numeric_features": NUMERIC, "IDENTIFIER_ONLY": IDS, "METADATA_ONLY": META,
          "FORBIDDEN": ["result_mean"], "TARGET": "imidacloprid_detected", "null_encoding": "\\N"}
    (root / "data/processed/synth.features.json").write_text(json.dumps(fm))
    parts = {}
    for name, (lo, hi) in CUTS.items():
        part = t[(t["collection_date"] >= lo) & (t["collection_date"] <= hi)]
        parts[name] = {"min_date": lo, "max_date": hi, "rows": len(part),
                       "target_counts": part["imidacloprid_detected"].value_counts().to_dict()}
    (root / "reports/m7.json").write_text(json.dumps({"split_audit": {"partitions": parts}}))
    r = {"model_ready": model_ready, "leakage_audit_passed": True, "target": "imidacloprid_detected",
         "dataset": "synth", "version": "1", "time_column": "collection_date", "group_column": "pdp_sample_id",
         "rows": n, "dataset_path": "data/processed/synth.csv",
         "feature_manifest_path": "data/processed/synth.features.json",
         "leakage_audit_path": "reports/m7.json", "readiness_scope": "RETROSPECTIVE_RELEASE_COHORT_ONLY",
         "prospective_deployment_ready": False, "observation_time": "2025-12-24", "schema_sha256": "x",
         "provenance_sha256": "x"}
    for path_key, sha_key in (("dataset_path", "dataset_sha256"), ("feature_manifest_path", "feature_manifest_sha256"),
                              ("leakage_audit_path", "leakage_audit_sha256")):
        r[sha_key] = sha256_file(root / r[path_key])
    out = root / "data/processed/synth.readiness.json"
    out.write_text(json.dumps(r))
    return out


def test_gate_drops_contract_excluded_features_and_reproduces_audit(tmp_path):
    h, audit = load_pdp_readiness(write_bundle(tmp_path))
    assert "pdp_collection_doy" not in h.features() and "pdp_collection_isoweek" not in h.features()
    assert "pdp_collection_dow_iso" in h.features("numeric") and len(h.features()) == 7
    parts = audited_split(h, audit)
    assert sum(len(v) for v in parts.values()) == len(h.table)
    assert parts["train"]["collection_date"].max() < parts["val"]["collection_date"].min()


@pytest.mark.parametrize("kwargs, error, match", [
    ({"model_ready": "true"}, NotModelReadyError, "model_ready"),             # string, not a JSON boolean
    ({"extra_column": "result_mean"}, ContractError, "undeclared columns"),   # outcome column slipped in
])
def test_gate_refuses_bad_bundles(tmp_path, kwargs, error, match):
    with pytest.raises(error, match=match):
        load_pdp_readiness(write_bundle(tmp_path, **kwargs))


def test_gate_refuses_tampered_dataset(tmp_path):
    path = write_bundle(tmp_path)
    with open(tmp_path / "data/processed/synth.csv", "a") as f:
        f.write("tampered\n")
    with pytest.raises(NotModelReadyError, match="sha256"):
        load_pdp_readiness(path)


def test_commodity_rate_is_smoothed_and_handles_unseen():
    X = pd.DataFrame({"pdp_commodity_code": ["A", "A", "B", "B"]})
    m = CommodityRate(k=2).fit(X, np.array([1, 1, 0, 0]))
    p = m.predict_proba(pd.DataFrame({"pdp_commodity_code": ["A", "B", "NEW"]}))[:, 1]
    assert p[0] == pytest.approx((2 + 2 * 0.5) / 4) and p[1] == pytest.approx(0.5 / 4 * 2) and p[2] == 0.5


def test_paired_bootstrap_identical_scores_give_zero():
    y, s = np.array([0, 1] * 50), np.linspace(0, 1, 100)
    r = paired_bootstrap_diff(average_precision_score, y, s, s, n=50)
    assert r["diff"] == 0 and r["ci"] == [0.0, 0.0] and r["share_a_better"] == 0


def test_run_chemical_end_to_end_is_flagged_synthetic(tmp_path, cfg):
    c = copy.deepcopy(cfg)
    c["chemical"]["imidacloprid"]["bootstrap"] = 30
    rep = run_chemical(c, readiness=write_bundle(tmp_path / "b"), reports_dir=tmp_path / "rep",
                       registry_dir=tmp_path / "reg")
    assert rep["synthetic"] is True and rep["selected_model"] in {"logistic_regression", "random_forest", "xgboost"}
    assert set(rep["vs_commodity_rate_pr_auc"]) == {"val", "test"}
    assert rep["ablation_with_calendar_position"]["added_features"] == ["pdp_collection_doy", "pdp_collection_isoweek"]
    meta = json.loads((tmp_path / "reg" / rep["model_version"] / "metadata.json").read_text())
    assert meta["domain"] == "CHEMICAL" and meta["scope"] == "RETROSPECTIVE_RELEASE_COHORT_ONLY"
    assert "pdp_collection_doy" not in meta["features"]["all"]
