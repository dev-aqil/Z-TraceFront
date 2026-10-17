"""Target contracts and the Person A -> Person B model-ready handoff gate.

A handoff is a JSON manifest next to a CSV table (format: reports/modeling_m8_handoff_contract.md at the repo
root). Nothing trains unless the manifest says model_ready: true (a JSON boolean), the table matches its SHA-256,
the target's contract status is READY, and every feature is declared available before the prediction time.
"""

import hashlib
import json
import platform
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import ROOT

TARGETS_FILE = ROOT / "configs" / "modeling" / "targets.toml"
FEATURE_DTYPES = {"categorical", "numeric", "boolean"}


class NotModelReadyError(RuntimeError):
    pass


class ContractError(ValueError):
    pass


def load_targets(path: Path = TARGETS_FILE) -> dict[str, Any]:
    with open(path, "rb") as f:
        return tomllib.load(f)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


@dataclass
class Handoff:
    manifest: dict[str, Any]
    table: pd.DataFrame
    contract: dict[str, Any]

    @property
    def target(self) -> str:
        return self.manifest["target_column"]

    def features(self, dtype: str | None = None) -> list[str]:
        return [f["name"] for f in self.manifest["features"] if dtype is None or f["dtype"] == dtype]


def load_handoff(manifest_path: str | Path, targets: dict[str, Any] | None = None) -> Handoff:
    """Validate a Person A handoff and load its table. Raises NotModelReadyError or ContractError."""
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        raise NotModelReadyError(f"no handoff manifest at {manifest_path}")
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    if m.get("model_ready") is not True:  # a JSON boolean, not "true" or 1
        raise NotModelReadyError(f"{manifest_path}: model_ready is {m.get('model_ready')!r}, not true")

    targets = targets or load_targets()
    name = m.get("target")
    if name not in targets["targets"]:
        context = "; ".join(f"{k}: {v}" for k, v in targets.get("non_targets", {}).items())
        raise ContractError(f"target {name!r} has no contract. Context-only sources are never targets ({context})")
    contract = targets["targets"][name]
    if contract["status"] != "READY":
        raise NotModelReadyError(f"target {name!r} contract status is {contract['status']}; training refused")
    if contract.get("requires_analyte") and not m.get("analyte"):
        raise ContractError(f"target {name!r} needs an analyte (one model per pathogen or pesticide)")

    table_meta = m["table"]
    table_path = (manifest_path.parent / table_meta["path"]).resolve()
    actual = sha256_file(table_path)
    if actual != table_meta["sha256"]:
        raise NotModelReadyError(f"{table_path.name}: sha256 {actual} does not match manifest {table_meta['sha256']}")
    table = pd.read_csv(table_path, dtype=str, keep_default_na=False, na_values=[table_meta.get("null_token", "")])
    if "row_count" in table_meta and len(table) != table_meta["row_count"]:
        raise NotModelReadyError(f"{table_path.name}: {len(table)} rows, manifest says {table_meta['row_count']}")

    validate_manifest(m, contract, list(table.columns))
    return Handoff(m, _type_columns(table, m, contract), contract)


def validate_manifest(m: dict[str, Any], contract: dict[str, Any], columns: list[str]) -> None:
    problems = []
    target, time_col = m.get("target_column"), m.get("prediction_time_column")
    features = m.get("features", [])
    names = [f.get("name") for f in features]
    labels = set(m.get("label_columns", [])) | {target}
    ids = set(m.get("id_columns", []))
    groups = {v for v in m.get("group_columns", {}).values() if v}

    for col in [target, time_col, *names, *labels, *ids, *groups]:
        if col not in columns:
            problems.append(f"declared column {col!r} not in table")
    if not names:
        problems.append("no features declared")
    if len(set(names)) != len(names):
        problems.append("duplicate feature names")
    for f in features:
        if f.get("dtype") not in FEATURE_DTYPES:
            problems.append(f"feature {f.get('name')!r}: dtype must be one of {sorted(FEATURE_DTYPES)}")
        if f.get("availability") != "pre_prediction":
            problems.append(f"feature {f.get('name')!r}: availability is {f.get('availability')!r}, not pre_prediction")
        if f.get("label_derived") and not f.get("history_cutoff"):
            problems.append(f"feature {f.get('name')!r}: label-derived history needs a declared history_cutoff")
    problems += [f"feature {n!r} is also a label/target column" for n in set(names) & labels]
    problems += [f"feature {n!r} is an identifier/grouping column" for n in set(names) & (ids | groups | {time_col})]
    for n in names:
        hits = [p for p in contract["forbidden_feature_patterns"] if p in str(n).lower()]
        if hits:
            problems.append(f"feature {n!r} matches forbidden pattern(s) {hits} for this target")
    if problems:
        raise ContractError("handoff violates the modeling contract:\n  - " + "\n  - ".join(problems))


def _type_columns(table: pd.DataFrame, m: dict[str, Any], contract: dict[str, Any]) -> pd.DataFrame:
    t = table.copy()
    t[m["prediction_time_column"]] = pd.to_datetime(t[m["prediction_time_column"]], format="ISO8601", utc=True)
    if t[m["prediction_time_column"]].isna().any():
        raise ContractError("prediction_time has missing or unparseable values")
    for f in m["features"]:
        if f["dtype"] == "numeric":
            t[f["name"]] = pd.to_numeric(t[f["name"]], errors="raise")
    y = t[m["target_column"]]
    if contract["task_type"] == "binary":
        codes = y.str.strip().str.casefold().map({"1": 1, "0": 0, "true": 1, "false": 0})
        if codes[y.notna()].isna().any():
            raise ContractError("binary target must be 0/1/true/false or empty")
        t[m["target_column"]] = codes.astype("Int8")
    elif contract["task_type"] == "regression":
        t[m["target_column"]] = pd.to_numeric(y, errors="raise")
    t = t[t[m["target_column"]].notna()].reset_index(drop=True)
    if contract["task_type"] == "binary":  # plain int: scikit-learn < 1.5 rejects nullable-integer object arrays
        t[m["target_column"]] = t[m["target_column"]].astype("int64")
    return t


def experiment_definition(handoff: Handoff, split: dict, seed: int, model_type: str, params: dict) -> dict:
    """Everything that defines an experiment. Its hash is the deterministic experiment_id."""
    m = handoff.manifest
    feature_list = sorted((f["name"], f["dtype"]) for f in m["features"])
    definition = {
        "dataset_id": m.get("dataset_id"), "dataset_version": m.get("dataset_version"),
        "dataset_sha256": m["table"]["sha256"], "feature_list_sha256": canonical_hash(feature_list),
        "target": m["target"], "analyte": m.get("analyte"), "target_contract_sha256": canonical_hash(handoff.contract),
        "split": split, "seed": seed, "model_type": model_type, "hyperparameters": params,
    }
    return {"experiment_id": canonical_hash(definition)[:16], **definition}


def run_environment() -> dict:
    """Where and when it ran. Kept apart from the definition so the same experiment on x86_64 and s390x
    shares one experiment_id."""
    import sklearn  # local: keep module import light
    return {
        "trained_at": datetime.now(UTC).isoformat(), "python": platform.python_version(),
        "machine": platform.machine(), "byteorder": sys.byteorder, "platform": platform.platform(),
        "sklearn": sklearn.__version__, "pandas": pd.__version__,
    }
