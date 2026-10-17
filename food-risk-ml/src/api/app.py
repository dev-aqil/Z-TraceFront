"""FastAPI inference service.

Run:  uvicorn src.api.app:app --port 8100
Model: $FOOD_RISK_MODEL_DIR if set, else the LATEST entry in the registry of $FOOD_RISK_PATHOGEN
(a config pathogen key such as salmonella or campylobacter; default: the config's default_pathogen).
The /models routes (src/api/spin.py) serve every pathogen model at once for the frontend's spin demo.
"""

import logging
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.api.schemas import PredictRequest
from src.api.spin import default_catalog, spin_router
from src.config import load_config, resolve
from src.models.predict import Predictor, UnsupportedFeatureError
from src.models.registry import latest_model_dir

log = logging.getLogger(__name__)


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


def create_app(model_dir: Path | None = None, spin_catalog=default_catalog) -> FastAPI:
    app = FastAPI(title="Food contamination risk: pathogen sample positivity", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("FOOD_RISK_CORS", "http://localhost:3000").split(","),
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(spin_router(spin_catalog))
    state: dict = {"predictor": None, "error": None}
    try:
        if model_dir is None:
            cfg = load_config(pathogen=os.environ.get("FOOD_RISK_PATHOGEN"))
            model_dir = Path(os.environ["FOOD_RISK_MODEL_DIR"]) if "FOOD_RISK_MODEL_DIR" in os.environ \
                else latest_model_dir(resolve(cfg["paths"]["registry"]))
        state["predictor"] = Predictor(model_dir)
    except Exception as e:  # missing file, missing library (e.g. xgboost on s390x), version-incompatible pickle
        state["error"] = f"{type(e).__name__}: {e}"
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
