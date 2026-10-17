"""Product-family routes, on the SYNTHETIC fixture model: code checks, not evaluation results."""

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.spin import load_family
from src.models.registry import latest_model_dir
from tests.synthetic import make_synthetic_canonical


@pytest.fixture(scope="module")
def setup(trained, cfg, tmp_path_factory):
    csv = tmp_path_factory.mktemp("spin") / "canonical.csv"
    df = make_synthetic_canonical()
    df.to_csv(csv, index=False)
    model_dir = latest_model_dir(trained["root"] / "registry")
    window = (cfg["split"]["val_start"], cfg["backtest"]["sealed_test_start"])
    # one family, two pathogen models: the same synthetic model twice stands in for e.g. Salmonella + Campylobacter
    family = load_family("Synthetic", [("synth_a", "Pathogen A", model_dir, csv), ("synth_b", "Pathogen B", model_dir, csv)],
                         *window)
    catalog = {"synthetic": family, "broken": "FileNotFoundError: no registry"}
    labels = df.assign(sample_date=df.sample_date.dt.strftime("%Y-%m-%d")).set_index("sample_id")["pathogen_positive"]
    return TestClient(create_app(model_dir, spin_catalog=lambda: catalog)), family, window, labels


def test_models_lists_families_with_their_models_and_reels(setup):
    client, _, (start, end), _ = setup
    body = client.get("/models").json()
    [fam] = body["families"]
    assert fam["key"] == "synthetic" and [m["pathogen"] for m in fam["models"]] == ["Pathogen A", "Pathogen B"]
    assert "broken" in body["unavailable"]
    reels = {f["name"]: f["options"] for f in fam["fields"]}
    assert {"sample_date", "product_category", "establishment_id", "meta_num_synthetic_score"} <= set(reels)
    assert all(start <= d < end for d in reels["sample_date"])


def test_legacy_salmonella_table_keeps_its_labels(trained, cfg, tmp_path):
    df = make_synthetic_canonical()
    csv = tmp_path / "legacy.csv"
    df.rename(columns={"pathogen_positive": "salmonella_positive"}).to_csv(csv, index=False)
    model_dir = latest_model_dir(trained["root"] / "registry")
    window = (cfg["split"]["val_start"], cfg["backtest"]["sealed_test_start"])
    family = load_family("Poultry", [("salmonella", "Salmonella", model_dir, csv)], *window)
    actual = family.pool.set_index("sample_id")["label:salmonella"].astype(int)
    expected = df.set_index("sample_id")["pathogen_positive"].loc[actual.index].astype(int)
    assert actual.equals(expected.rename("label:salmonella"))
    with pytest.raises(ValueError, match="missing its pathogen_positive label"):
        load_family("Wrong pathogen", [("campylobacter", "Campylobacter", model_dir, csv)], *window)


def test_spin_runs_every_family_model_on_one_validation_sample(setup):
    client, family, (start, end), labels = setup
    for _ in range(20):
        body = client.post("/models/spin", json={}).json()
        assert start <= body["sample"]["sample_date"] < end  # never the sealed test window
        assert [r["model"] for r in body["results"]] == ["synth_a", "synth_b"]
        truth = "positive" if labels[body["sample_id"]] == 1 else "negative"
        assert all(r["actual"] == truth for r in body["results"])  # each model gets its own real label
    direct = family.members[0][2].predict([body["sample"]])[0]["probability_positive"]
    assert body["results"][0]["prediction"]["probability_positive"] == pytest.approx(direct)


def test_predict_picks_the_family_from_the_programme_alone(setup):
    client, _, _, _ = setup
    body = client.post("/models/predict", json={"sample_date": "2023-03-01", "product_category": "synthetic_parts",
                                                "establishment_id": "SYNTH-EST-001"}).json()
    assert body["family"] == "synthetic" and len(body["results"]) == 2
    assert all(r["actual"] is None for r in body["results"])  # entered details have no lab result


def test_predict_without_a_programme_needs_the_family(setup):
    client, _, _, _ = setup
    assert client.post("/models/predict", json={"sample_date": "2023-03-01"}).status_code == 422
    assert client.post("/models/predict?family=synthetic", json={"sample_date": "2023-03-01"}).status_code == 200


@pytest.mark.parametrize("path, payload, status", [
    ("/models/predict", {"sample_date": "2023-03-01", "product_category": "MT43"}, 422),         # another family's code
    ("/models/predict?family=nope", {"sample_date": "2023-03-01"}, 404),
    ("/models/predict?family=broken", {"sample_date": "2023-03-01"}, 503),
    ("/models/predict?family=synthetic", {"sample_date": "2023-03-01", "metadata": {"meta_cat_recall": "Y"}}, 422),
    ("/models/spin", {"family": "synthetic", "pathogen_positive": 1}, 422),
])
def test_rejects_bad_requests(setup, path, payload, status):
    client, _, _, _ = setup
    assert client.post(path, json=payload).status_code == status
