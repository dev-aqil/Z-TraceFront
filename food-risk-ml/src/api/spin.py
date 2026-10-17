"""Product-family routes for the frontend demo: enter or spin one sample's details, and every pathogen model for its
product runs on it. Raw poultry -> Salmonella + Campylobacter, raw beef -> Salmonella + STEC, ready-to-eat ->
Listeria. Each model reports separately; they are never combined into one score (model cards).

The family is identified by the FSIS programme code alone: the codes of the three families are disjoint. A model is
never run on another family's sample, because it learned nothing about that product and would ignore its codes.

Spins draw a real sample from the validation window [split.val_start, backtest.sealed_test_start) and return each
pathogen's actual lab result: every sample in a family was tested for all of its pathogens. Those samples were never
trained on, but they chose the models, calibration and thresholds, so results there are slightly optimistic. The
sealed test window is never served: it is scored exactly once, for the final model.
"""

import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from src.api.schemas import PredictRequest
from src.config import load_config, resolve
from src.data.contract import ESTABLISHMENT_ID, PRODUCT_CATEGORY, SAMPLE_DATE, SAMPLE_ID, TARGET, UNKNOWN_CATEGORY
from src.models.predict import Predictor
from src.models.registry import latest_model_dir

log = logging.getLogger(__name__)

# family key -> (display name, [(config pathogen key, pathogen display name)])
FAMILIES = {
    "poultry": ("Raw poultry", [("salmonella", "Salmonella"), ("campylobacter", "Campylobacter")]),
    "beef": ("Raw beef", [("beef_salmonella", "Salmonella"), ("beef_stec", "STEC")]),
    "rte": ("Ready-to-eat products", [("rte_listeria", "Listeria monocytogenes")]),
}
LABELS = {
    SAMPLE_DATE: "Sample date",
    PRODUCT_CATEGORY: "FSIS programme",
    ESTABLISHMENT_ID: "Establishment",
    "meta_cat_sample_source_name": "Sample source",
    "meta_cat_product_type": "Product type",
    "meta_cat_production_alternative": "Production alternative",
    "meta_cat_establishment_state": "State",
    "sample_month": "Sample month",
    "est_prior_samples": "Establishment's past samples",
    "est_prior_positives": "Establishment's past positives",
    "est_prior_rate_smoothed": "Establishment's past positive rate",
    "est_days_since_prior": "Days since the establishment's last sample",
}


@dataclass
class Family:
    name: str
    members: list[tuple[str, str, Predictor]]  # (model key, pathogen name, predictor)
    pool: pd.DataFrame  # validation-window samples with one "label:<model key>" column per member
    fields: list[str]
    options: dict[str, list[str]]  # every value of each field seen in the pool: the reels
    programmes: set[str]  # every FSIS programme code in the family's data, all dates
    window: tuple[str, str]


def load_family(name: str, members: list[tuple[str, str, Path, Path]], start: str, end: str) -> Family:
    """members: (model key, pathogen name, model dir, canonical csv). Keeps samples labelled for every member."""
    loaded, fields, programmes, pool = [], [], set(), None
    for key, pathogen, model_dir, processed in members:
        predictor = Predictor(model_dir)
        wanted = [SAMPLE_DATE, PRODUCT_CATEGORY, ESTABLISHMENT_ID, *predictor.meta_features]
        df = pd.read_csv(processed, dtype=str, usecols=lambda c: c in {SAMPLE_ID, TARGET, *wanted})
        df[SAMPLE_DATE] = df[SAMPLE_DATE].str[:10]
        programmes |= set(df[PRODUCT_CATEGORY].dropna()) - {UNKNOWN_CATEGORY}
        rows = df[(df[SAMPLE_DATE] >= start) & (df[SAMPLE_DATE] < end) & df[TARGET].isin(["0", "1"])]
        rows = rows.drop_duplicates(SAMPLE_ID).rename(columns={TARGET: f"label:{key}"})
        if pool is None:
            pool = rows
        else:
            pool = pool.merge(rows[[SAMPLE_ID, f"label:{key}", *(c for c in wanted if c in rows and c not in pool)]],
                              on=SAMPLE_ID)
        fields += [f for f in wanted if f not in fields]
        loaded.append((key, pathogen, predictor))
    pool = pool.reset_index(drop=True)
    if pool.empty:
        raise ValueError(f"no samples labelled for every {name} model from {start} to before {end}")
    fields = [f for f in fields if f in pool]
    return Family(name, loaded, pool, fields, {f: sorted(pool[f].dropna().unique().tolist()) for f in fields},
                  programmes, (start, end))


@cache
def default_catalog() -> dict[str, Family | str]:
    """Every product family with its models and pool, loaded on first use; a family that cannot load maps to the error."""
    out: dict[str, Family | str] = {}
    for key, (name, pathogens) in FAMILIES.items():
        try:
            members, cfg = [], None
            for model_key, pathogen in pathogens:
                cfg = load_config(pathogen=model_key)
                members.append((model_key, pathogen, latest_model_dir(resolve(cfg["paths"]["registry"])),
                                resolve(cfg["paths"]["processed"])))
            out[key] = load_family(name, members, cfg["split"]["val_start"], cfg["backtest"]["sealed_test_start"])
        except Exception as e:  # missing registry or processed data, version-incompatible pickle
            out[key] = f"{type(e).__name__}: {e}"
            log.warning("spin: %s unavailable: %s", key, e)
    return out


class SpinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    family: str | None = None  # a FAMILIES key; random when omitted


def spin_router(catalog: Callable[[], dict[str, Family | str]]) -> APIRouter:
    router = APIRouter(prefix="/models")

    def available() -> dict[str, Family]:
        return {k: v for k, v in catalog().items() if isinstance(v, Family)}

    def family_of(key: str) -> Family:
        f = available().get(key)
        if f is None:
            raise HTTPException(503 if key in catalog() else 404, f"product family {key!r} is not available")
        return f

    def run(key: str, f: Family, record: dict, sample_id: str | None = None, row: pd.Series | None = None) -> dict:
        unknown = set(record["metadata"]) - {m for _, _, p in f.members for m in p.meta_features}
        if unknown:
            raise HTTPException(422, f"unsupported metadata fields {sorted(unknown)} for {f.name}")
        results = []
        for model_key, pathogen, predictor in f.members:
            own = {**record, "metadata": {k: v for k, v in record["metadata"].items() if k in predictor.meta_features}}
            actual = None if row is None else "positive" if row[f"label:{model_key}"] == "1" else "negative"
            results.append({"model": model_key, "pathogen": pathogen, "actual": actual,
                            "prediction": predictor.predict([own])[0]})
        return {"family": key, "name": f.name, "sample_id": sample_id, "sample": record,
                "window": {"start": f.window[0], "end": f.window[1]}, "results": results}

    @router.get("")
    def models() -> dict:
        cat = catalog()
        return {"families": [{"key": k, "name": f.name, "models": [{"key": m, "pathogen": p} for m, p, _ in f.members],
                              "fields": [{"name": n, "label": LABELS.get(n, n), "options": f.options[n]} for n in f.fields]}
                             for k, f in cat.items() if isinstance(f, Family)],
                "labels": LABELS, "unavailable": {k: v for k, v in cat.items() if isinstance(v, str)}}

    @router.post("/spin")
    def spin(req: SpinRequest) -> dict:
        ready = available()
        if not ready:
            raise HTTPException(503, "no product family is available")
        key = req.family or random.choice(list(ready))
        f = family_of(key)
        row = f.pool.iloc[random.randrange(len(f.pool))]

        def value(name: str):
            return None if name not in row or pd.isna(row[name]) else row[name]

        meta = {m for _, _, p in f.members for m in p.meta_features}
        record = {"sample_date": row[SAMPLE_DATE], "product_category": value(PRODUCT_CATEGORY),
                  "establishment_id": value(ESTABLISHMENT_ID), "metadata": {m: value(m) for m in sorted(meta)}}
        return run(key, f, record, row[SAMPLE_ID], row)

    @router.post("/predict")
    def predict(req: PredictRequest, family: str | None = None) -> dict:
        """The real-world entry: one sample's details in, every model for its product out. The FSIS programme code
        picks the family; ?family= is needed only when the programme is not recorded."""
        code = req.product_category
        if code is not None:
            owners = [k for k, f in available().items() if code in f.programmes]
            if not owners:
                raise HTTPException(422, f"{code!r} is not an FSIS programme of any loaded model")
            if family is not None and family not in owners:
                raise HTTPException(422, f"programme {code!r} belongs to {owners[0]}, not {family}")
            family = family or owners[0]
        if family is None:
            raise HTTPException(422, "give the FSIS programme (product_category), or ?family=, so the right models run")
        return run(family, family_of(family), req.model_dump(mode="json"))

    return router
