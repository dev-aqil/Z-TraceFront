import pytest
from fastapi.testclient import TestClient

from src.api.app import PredictResponse, create_app
from src.models.registry import latest_model_dir


@pytest.fixture(scope="module")
def client(trained):
    return TestClient(create_app(latest_model_dir(trained["root"] / "registry")))


def test_health(client):
    r = client.get("/health").json()
    assert r["status"] == "ok" and r["pathogen"] == "Salmonella" and r["model_version"]


def test_predict_response_schema(client):
    r = client.post("/predict", json={"sample_date": "2024-01-15", "product_category": "synthetic_parts",
                                      "establishment_id": "SYNTH-EST-003",
                                      "metadata": {"meta_num_synthetic_score": 0.3}})
    assert r.status_code == 200
    body = PredictResponse(**r.json())
    assert set(r.json()) >= {"model_version", "pathogen", "probability_positive", "risk_band", "threshold",
                             "explanation"}
    assert body.explanation is None or all(isinstance(c.contribution, float) for c in body.explanation)


@pytest.mark.parametrize("payload", [
    {"product_category": "x"},                                           # missing sample_date
    {"sample_date": "not-a-date"},
    {"sample_date": "2024-01-15", "pathogen_positive": 1},             # unknown top-level field
    {"sample_date": "2024-01-15", "metadata": {"meta_cat_recall_flag": "Y"}},  # feature the model lacks
])
def test_predict_rejects_invalid_input(client, payload):
    assert client.post("/predict", json=payload).status_code == 422


def test_no_model_mode(tmp_path):
    c = TestClient(create_app(tmp_path / "missing"))
    assert c.get("/health").json()["status"] == "no_model"
    assert c.post("/predict", json={"sample_date": "2024-01-15"}).status_code == 503
