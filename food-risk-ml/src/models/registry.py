"""File-based model registry: artifacts/registry/<version>/ holds everything inference needs.

  model.joblib        complete fitted preprocessing+model pipeline (Platt-wrapped if calibrated)
  metadata.json       version, provenance, features, threshold, bands, metrics, library versions
  history.csv         per-establishment daily sample/positive counts used for history features
  background.csv      small sample of training feature rows (SHAP background for linear models)
LATEST (in the registry root) names the most recently registered version.
"""

import json
import logging
from pathlib import Path

import joblib
import pandas as pd

from src.data.contract import ESTABLISHMENT_ID, SAMPLE_DATE

log = logging.getLogger(__name__)


def save_model(registry: Path, model, metadata: dict, history: pd.DataFrame | None,
               background: pd.DataFrame) -> Path:
    out = Path(registry) / metadata["model_version"]
    out.mkdir(parents=True, exist_ok=False)
    joblib.dump(model, out / "model.joblib")
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str))
    if history is not None:
        history.to_csv(out / "history.csv", index=False)
    background.to_csv(out / "background.csv", index=False)
    (Path(registry) / "LATEST").write_text(metadata["model_version"])
    log.info("registered %s", out)
    return out


def latest_model_dir(registry: Path) -> Path:
    pointer = Path(registry) / "LATEST"
    if not pointer.exists():
        raise FileNotFoundError(f"no registered model in {registry} (run `python -m src.cli train` first)")
    return Path(registry) / pointer.read_text().strip()


def load_model(model_dir: Path) -> tuple[object, dict, pd.DataFrame | None, pd.DataFrame]:
    model_dir = Path(model_dir)
    meta = json.loads((model_dir / "metadata.json").read_text())
    history = None
    if (model_dir / "history.csv").exists():
        history = pd.read_csv(model_dir / "history.csv", dtype={ESTABLISHMENT_ID: str}, parse_dates=[SAMPLE_DATE])
    background = pd.read_csv(model_dir / "background.csv", keep_default_na=False, na_values=[""])
    for c in meta["features"]["categorical"]:
        background[c] = background[c].astype(str)
    return joblib.load(model_dir / "model.joblib"), meta, history, background
