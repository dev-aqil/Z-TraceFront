"""FastAPI inference service.

Run:  uvicorn src.api.app:app --port 8100
Model: $FOOD_RISK_MODEL_DIR if set, else the LATEST entry in artifacts/registry.
"""

import logging
import os
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.config import load_config, resolve
from src.models.predict import Predictor, UnsupportedFeatureError
from src.models.registry import latest_model_dir

log = logging.getLogger(__name__)


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sample_date: date = Field(description="Planned/actual sample collection date")
    product_category: str | None = Field(None, description="Product category as in the training data")
    establishment_id: str | None = Field(None, description="Establishment identifier; enables history features")
    metadata: dict[str, str | float | None] = Field(
        default_factory=dict, description="Extra pre-sampling features declared at training (meta_cat_/meta_num_)")


class Contribution(BaseModel):
    feature: str
    source_feature: str
    input_value: str | None
    contribution: float


class PredictResponse(BaseModel):
    model_version: str
    pathogen: str
    probability_positive: float
    risk_band: Literal["high", "medium", "low"]
    threshold: float
    explanation: list[Contribution] | None
    explanation_units: str | None
    trained_on_synthetic_data: bool
    disclaimer: str


class Health(BaseModel):
    status: Literal["ok", "no_model"]
    model_version: str | None = None
    pathogen: str | None = None
    detail: str | None = None


def create_app(model_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Food contamination risk: Salmonella sample positivity", version="0.1.0")
    state: dict = {"predictor": None, "error": None}
    try:
        if model_dir is None:
            model_dir = Path(os.environ["FOOD_RISK_MODEL_DIR"]) if "FOOD_RISK_MODEL_DIR" in os.environ \
                else latest_model_dir(resolve(load_config()["paths"]["registry"]))
        state["predictor"] = Predictor(model_dir)
    except (FileNotFoundError, OSError) as e:
        state["error"] = str(e)
        log.warning("starting without a model: %s", e)

    @app.get("/health", response_model=Health)
    def health() -> Health:
        p = state["predictor"]
        if p is None:
            return Health(status="no_model", detail=state["error"])
        return Health(status="ok", model_version=p.meta["model_version"], pathogen=p.meta["pathogen"])

    @app.post("/predict", response_model=PredictResponse)
    def predict(req: PredictRequest) -> PredictResponse:
        p = state["predictor"]
        if p is None:
            raise HTTPException(503, f"no model loaded: {state['error']}")
        try:
            return PredictResponse(**p.predict([req.model_dump()])[0])
        except UnsupportedFeatureError as e:
            raise HTTPException(422, str(e)) from e

    return app


app = create_app()
