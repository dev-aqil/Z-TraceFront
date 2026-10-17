"""Inference from a registered model directory."""

from pathlib import Path

import pandas as pd

from src.data.contract import ESTABLISHMENT_ID, PRODUCT_CATEGORY, SAMPLE_DATE, UNKNOWN_CATEGORY
from src.explainability.shap_explain import Explainer
from src.features.build import make_features
from src.models.registry import load_model

DISCLAIMER = (
    "Estimated probability that a laboratory sample with these characteristics tests positive for the named "
    "pathogen, learned from historical sampling records. It is a prioritisation signal for sampling and "
    "inspection, not a food-safety certification: a low score does not mean a product is safe. Explanations "
    "describe model behaviour, not causes of contamination."
)


class UnsupportedFeatureError(ValueError):
    pass


class Predictor:
    def __init__(self, model_dir: str | Path):
        self.model, self.meta, self.history, background = load_model(Path(model_dir))
        pipeline = getattr(self.model, "pipeline", self.model)  # unwrap Platt calibration for SHAP
        self.explainer = Explainer(pipeline, background)
        self.meta_features = [c for c in self.meta["features"]["all"] if c.startswith("meta_")]

    def risk_band(self, p: float) -> str:
        b = self.meta["risk_bands"]
        return "high" if p >= b["high_from"] else "medium" if p >= b["medium_from"] else "low"

    def predict(self, records: list[dict], explain: bool = True) -> list[dict]:
        unknown = sorted({k for r in records for k in r.get("metadata", {})} - set(self.meta_features))
        if unknown:
            raise UnsupportedFeatureError(f"unsupported metadata fields {unknown}; this model accepts {self.meta_features}")
        df = pd.DataFrame({
            SAMPLE_DATE: pd.to_datetime([r["sample_date"] for r in records]),
            PRODUCT_CATEGORY: [r.get("product_category") or UNKNOWN_CATEGORY for r in records],
            ESTABLISHMENT_ID: [r.get("establishment_id") for r in records],
        })
        for c in self.meta_features:
            df[c] = [r.get("metadata", {}).get(c) for r in records]
        f = self.meta["features"]
        X = make_features(df, self.history if f["uses_history"] else None,
                          {"features": f["history_params"]}, f["prior_rate"])[f["all"]]
        for c in f["numeric"]:
            X[c] = pd.to_numeric(X[c], errors="coerce")
        probs = self.model.predict_proba(X)[:, 1]
        expl = self.explainer.local(X, self.meta["explain_top_k"]) if explain and self.explainer.supported \
            else [None] * len(X)
        return [{
            "model_version": self.meta["model_version"],
            "pathogen": self.meta["pathogen"],
            "probability_positive": float(p),
            "risk_band": self.risk_band(float(p)),
            "threshold": self.meta["threshold"],
            "explanation": e,
            "explanation_units": self.explainer.units if e is not None else None,
            "trained_on_synthetic_data": self.meta["provenance"]["synthetic"],
            "disclaimer": DISCLAIMER,
        } for p, e in zip(probs, expl, strict=True)]
