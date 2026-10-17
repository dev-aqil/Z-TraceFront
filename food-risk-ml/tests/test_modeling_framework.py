"""Modeling framework tests. SYNTHETIC handoffs only; nothing here reads Person A's M1/M2 data."""

import copy
import json

import numpy as np
import pandas as pd
import pytest

from src.evaluation import splits
from src.evaluation.metrics import binary_metrics, multiclass_metrics, regression_metrics
from src.models.contracts import (
    ContractError,
    NotModelReadyError,
    experiment_definition,
    load_handoff,
    load_targets,
    sha256_file,
)
from src.models.experiment import run_experiment

FEATURES = [
    {"name": "food_category", "dtype": "categorical", "availability": "pre_prediction", "label_derived": False},
    {"name": "storage_avg_temp_c", "dtype": "numeric", "availability": "pre_prediction", "label_derived": False},
    {"name": "previous_test_count", "dtype": "numeric", "availability": "pre_prediction", "label_derived": True,
     "history_cutoff": "prediction_time - 7 days"},
]


def ready_targets(name: str = "pathogen_positive") -> dict:
    t = copy.deepcopy(load_targets())
    t["targets"][name]["status"] = "READY"  # test-only override; the real file keeps every target blocked
    return t


def synthetic_table(n: int = 600, seed: int = 0, regression: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    temp = rng.normal(4, 3, n)
    logit = -2 + 0.4 * temp
    return pd.DataFrame({
        "observation_id": [f"SYNTH-{i}" for i in range(n)],
        "prediction_time": (pd.Timestamp("2024-01-01", tz="UTC") + pd.to_timedelta(np.sort(rng.integers(0, 500, n)),
                                                                                    unit="D")).astype(str),
        "factory_id": [f"SYNTH-F{x}" for x in rng.integers(0, 30, n)],
        "region": rng.choice(["R1", "R2", "R3", "R4"], n),
        "food_category": rng.choice(["synthetic_a", "synthetic_b"], n),
        "storage_avg_temp_c": temp.round(2),
        "previous_test_count": rng.integers(0, 20, n),
        "pathogen_positive": (temp * 0.5 + rng.normal(0, 1, n)).round(3) if regression
        else rng.binomial(1, 1 / (1 + np.exp(-logit))),
    })


def write_handoff(tmp_path, table: pd.DataFrame, target="pathogen_positive", **overrides) -> str:
    table.to_csv(tmp_path / "table.csv", index=False)
    manifest = {
        "handoff_version": "1", "model_ready": True, "target": target, "analyte": "SYNTHETIC",
        "target_column": "pathogen_positive", "dataset_id": "synthetic", "dataset_version": "test",
        "table": {"path": "table.csv", "sha256": sha256_file(tmp_path / "table.csv"), "row_count": len(table)},
        "prediction_time_column": "prediction_time", "group_columns": {"facility": "factory_id"},
        "id_columns": ["observation_id"], "label_columns": ["pathogen_positive"], "features": FEATURES,
        "is_synthetic": True,
    }
    manifest.update(overrides)
    (tmp_path / "handoff.json").write_text(json.dumps(manifest))
    return str(tmp_path / "handoff.json")


# --- training refuses anything not explicitly model-ready -------------------------------------------------------

def test_refuses_missing_manifest(tmp_path):
    with pytest.raises(NotModelReadyError, match="no handoff manifest"):
        load_handoff(tmp_path / "nope.json", ready_targets())


@pytest.mark.parametrize("flag", [False, "true", 1, None])
def test_refuses_unless_model_ready_is_json_true(tmp_path, flag):
    with pytest.raises(NotModelReadyError, match="model_ready"):
        load_handoff(write_handoff(tmp_path, synthetic_table(), model_ready=flag), ready_targets())


def test_refuses_table_changed_after_handoff(tmp_path):
    path = write_handoff(tmp_path, synthetic_table())
    with open(tmp_path / "table.csv", "a") as f:
        f.write("tampered\n")
    with pytest.raises(NotModelReadyError, match="sha256"):
        load_handoff(path, ready_targets())


def test_every_real_target_is_currently_blocked(tmp_path):
    targets = load_targets()
    assert all(c["status"] != "READY" for c in targets["targets"].values())
    with pytest.raises(NotModelReadyError, match="contract status"):
        load_handoff(write_handoff(tmp_path, synthetic_table()), targets)


@pytest.mark.parametrize("target", ["recall_status", "inspection_classification", "pathogen_contamination"])
def test_refuses_targets_without_a_contract(tmp_path, target):
    with pytest.raises(ContractError, match="no contract"):
        load_handoff(write_handoff(tmp_path, synthetic_table(), target=target), ready_targets())


def test_pathogen_target_needs_an_analyte(tmp_path):
    with pytest.raises(ContractError, match="analyte"):
        load_handoff(write_handoff(tmp_path, synthetic_table(), analyte=None), ready_targets())


# --- leakage: target, labels, ids and forbidden columns never become features -------------------------------------

def _feature(name, **kw):
    return {"name": name, "dtype": "numeric", "availability": "pre_prediction", "label_derived": False, **kw}


@pytest.mark.parametrize("bad_feature, message", [
    (_feature("pathogen_positive"), "also a label"),
    (_feature("observation_id", dtype="categorical"), "identifier"),
    (_feature("factory_id", dtype="categorical"), "identifier"),
    (_feature("serotype_code", dtype="categorical"), "forbidden pattern"),
    (_feature("recall_status", dtype="categorical"), "forbidden pattern"),
    (_feature("storage_avg_temp_c", availability="post_prediction"), "not pre_prediction"),
    (_feature("storage_avg_temp_c", availability=None), "not pre_prediction"),
    (_feature("previous_test_count", label_derived=True), "history_cutoff"),
])
def test_rejects_leaky_feature_declarations(tmp_path, bad_feature, message):
    t = synthetic_table().assign(serotype_code="x", recall_status="x")
    feats = [f for f in FEATURES if f["name"] != bad_feature["name"]] + [bad_feature]
    with pytest.raises(ContractError, match=message):
        load_handoff(write_handoff(tmp_path, t, features=feats), ready_targets())


def test_chemical_target_rejects_same_sample_concentration(tmp_path):
    t = synthetic_table().assign(concen_ppm=0.1)
    feats = FEATURES + [_feature("concen_ppm")]
    with pytest.raises(ContractError, match="forbidden pattern"):
        load_handoff(write_handoff(tmp_path, t, target="pesticide_detected", features=feats),
                     ready_targets("pesticide_detected"))


def test_loaded_feature_matrix_excludes_target(tmp_path):
    h = load_handoff(write_handoff(tmp_path, synthetic_table()), ready_targets())
    assert h.target not in h.features() and h.table[h.target].isin([0, 1]).all()


# --- splits ----------------------------------------------------------------------------------------------------------

def test_temporal_split_preserves_chronology():
    df = synthetic_table().assign(prediction_time=lambda d: pd.to_datetime(d["prediction_time"]))
    parts = splits.temporal_split(df, "prediction_time", 0.7, 0.15)
    splits.assert_split_integrity(parts, id_col="observation_id", time_col="prediction_time")
    assert parts["train"]["prediction_time"].max() < parts["val"]["prediction_time"].min()
    shuffled = {"train": parts["test"], "val": parts["val"], "test": parts["train"]}
    with pytest.raises(splits.SplitError, match="chronology"):
        splits.assert_split_integrity(shuffled, time_col="prediction_time")


def test_grouped_split_prevents_group_overlap():
    df = synthetic_table()
    parts = splits.grouped_split(df, "factory_id", 0.7, 0.15, seed=3)
    splits.assert_split_integrity(parts, id_col="observation_id", group_col="factory_id")
    assert sum(len(p) for p in parts.values()) == len(df)
    leaky = {"train": df.iloc[:400], "test": df.iloc[300:]}
    with pytest.raises(splits.SplitError):
        splits.assert_split_integrity(leaky, group_col="factory_id")


def test_geographic_holdout_and_random_split_guard():
    df = synthetic_table()
    parts = splits.geographic_holdout(df, "region", ["R4"], ["R3"])
    assert set(parts["test"]["region"]) == {"R4"} and not {"R3", "R4"} & set(parts["train"]["region"])
    with pytest.raises(splits.SplitError, match="refused"):
        splits.random_split(df, "pathogen_positive", 0.7, 0.15, seed=0)
    allowed = splits.random_split(df, "pathogen_positive", 0.7, 0.15, seed=0, allow_random=True)
    assert sum(len(p) for p in allowed.values()) == len(df)


# --- metrics on toy examples ---------------------------------------------------------------------------------------

def test_binary_metrics_toy():
    m = binary_metrics(np.array([1, 1, 0, 0]), np.array([0.9, 0.2, 0.8, 0.1]), threshold=0.5)
    assert (m["tp"], m["fn"], m["fp"], m["tn"]) == (1, 1, 1, 1)
    assert m["recall"] == 0.5 and m["false_negative_rate"] == 0.5 and m["specificity"] == 0.5


def test_regression_metrics_toy():
    m = regression_metrics(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 4.0]))
    assert m["mae"] == pytest.approx(1 / 3) and m["rmse"] == pytest.approx(np.sqrt(1 / 3))
    assert m["residual_mean"] == pytest.approx(-1 / 3)


def test_multiclass_metrics_toy():
    m = multiclass_metrics(np.array(["fresh", "fresh", "spoiled"]), np.array(["fresh", "spoiled", "spoiled"]),
                           ["fresh", "spoiled"])
    assert m["per_class_recall"] == {"fresh": 0.5, "spoiled": 1.0}
    assert m["confusion_matrix"] == [[1, 1], [0, 1]]


# --- reproducibility -----------------------------------------------------------------------------------------------

def test_experiment_definition_is_deterministic(tmp_path):
    h = load_handoff(write_handoff(tmp_path, synthetic_table()), ready_targets())
    split = {"method": "temporal", "train_frac": 0.7}
    a = experiment_definition(h, split, 42, "logistic_regression", {"C": 1.0})
    b = experiment_definition(h, dict(split), 42, "logistic_regression", {"C": 1.0})
    assert a == b
    assert experiment_definition(h, split, 7, "logistic_regression", {"C": 1.0})["experiment_id"] != a["experiment_id"]
    assert "trained_at" not in a and "machine" not in a  # environment is recorded separately


@pytest.mark.parametrize("use_xgboost", [True, False])
def test_end_to_end_binary_experiment_on_synthetic_handoff(tmp_path, use_xgboost):
    res = run_experiment(write_handoff(tmp_path, synthetic_table()), tmp_path / "out", targets=ready_targets(),
                         use_xgboost=use_xgboost)
    models = {r["model_type"] for r in res["runs"]}
    assert {"dummy_prior", "logistic_regression", "random_forest", "hist_gradient_boosting"} <= models
    assert res["synthetic"] is True and res["split"]["method"] == "temporal"
    assert 0 <= res["split"]["test_rows_from_unseen_groups"] <= 1
    assert {"pr_auc", "recall", "false_negative_rate", "brier"} <= set(res["runs"][0]["metrics"]["test"])
    again = run_experiment(write_handoff(tmp_path, synthetic_table()), tmp_path / "out", targets=ready_targets(),
                           use_xgboost=use_xgboost)
    assert [r["experiment_id"] for r in again["runs"]] == [r["experiment_id"] for r in res["runs"]]


def test_end_to_end_regression_experiment_grouped(tmp_path):
    t = ready_targets("microbial_count")
    path = write_handoff(tmp_path, synthetic_table(regression=True), target="microbial_count", analyte=None,
                         features=[f for f in FEATURES if f["name"] != "previous_test_count"])
    res = run_experiment(path, tmp_path / "out", targets=t, split_overrides={"group_column": "factory_id"},
                         use_xgboost=False)
    assert res["split"]["method"] == "grouped"
    assert {"mae", "rmse", "r2"} <= set(res["runs"][0]["metrics"]["test"])
