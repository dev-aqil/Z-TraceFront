import copy

import pytest

from src.config import load_config
from src.models.train import run_training
from tests.synthetic import make_synthetic_canonical


@pytest.fixture(scope="session")
def cfg():
    c = copy.deepcopy(load_config())
    c["models"]["random_forest"]["n_estimators"] = 30
    c["models"]["xgboost"]["n_estimators"] = 30
    c["explain"]["shap_sample"] = 100
    return c


@pytest.fixture
def synthetic_df():
    return make_synthetic_canonical()


@pytest.fixture(scope="session")
def trained(cfg, tmp_path_factory):
    """Train once on SYNTHETIC data into a temporary registry (code test only)."""
    root = tmp_path_factory.mktemp("run")
    report = run_training(make_synthetic_canonical(), cfg, root / "reports", root / "registry",
                          {"canonical_file": "synthetic-fixture"})
    return {"report": report, "root": root}
