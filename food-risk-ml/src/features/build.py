"""Model features: calendar, product, declared pre-sampling metadata, and time-guarded establishment history."""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.data.contract import (
    ESTABLISHMENT_ID,
    PRODUCT_CATEGORY,
    SAMPLE_DATE,
    TARGET,
    UNKNOWN_CATEGORY,
    meta_columns,
)

HISTORY_FEATURES = ("est_prior_samples", "est_prior_positives", "est_prior_rate_smoothed", "est_days_since_prior")
CALENDAR_FEATURES = ("sample_month",)


def build_daily_history(labelled: pd.DataFrame) -> pd.DataFrame:
    """Per establishment and collection date: number of labelled samples and positives."""
    h = labelled.dropna(subset=[ESTABLISHMENT_ID, SAMPLE_DATE, TARGET])
    daily = (h.groupby([ESTABLISHMENT_ID, SAMPLE_DATE])[TARGET].agg(n="size", pos="sum").reset_index())
    daily["pos"] = daily["pos"].astype(int)
    return daily


def add_history_features(df: pd.DataFrame, daily: pd.DataFrame, lag_days: int, prior_rate: float,
                         smoothing: float) -> pd.DataFrame:
    """Establishment history from strictly earlier, already-reported results only.

    A labelled sample collected on date d counts for a sample on date t iff d + lag_days < t. Same-day and
    later samples (including the sample itself) never contribute. The rate is shrunk toward prior_rate
    (the training-set positive rate) with `smoothing` pseudo-samples so sparse histories stay near the mean.
    """
    d = daily.sort_values([ESTABLISHMENT_ID, SAMPLE_DATE]).copy()
    d[SAMPLE_DATE] = d[SAMPLE_DATE].astype("datetime64[ns]")  # merge_asof needs identical datetime units
    d["cum_n"] = d.groupby(ESTABLISHMENT_ID)["n"].cumsum()
    d["cum_pos"] = d.groupby(ESTABLISHMENT_ID)["pos"].cumsum()
    d["available_from"] = d[SAMPLE_DATE] + pd.Timedelta(days=lag_days)
    d = d.rename(columns={SAMPLE_DATE: "_prior_date"})[[ESTABLISHMENT_ID, "available_from", "_prior_date",
                                                         "cum_n", "cum_pos"]]

    left = df[[ESTABLISHMENT_ID, SAMPLE_DATE]].astype({SAMPLE_DATE: "datetime64[ns]"})
    left["_row"] = np.arange(len(df))
    ok = left[ESTABLISHMENT_ID].notna() & left[SAMPLE_DATE].notna()
    merged = pd.merge_asof(
        left[ok].astype({ESTABLISHMENT_ID: str}).sort_values(SAMPLE_DATE),
        d.astype({ESTABLISHMENT_ID: str}).sort_values("available_from"),
        left_on=SAMPLE_DATE, right_on="available_from", by=ESTABLISHMENT_ID,
        direction="backward", allow_exact_matches=False,  # strict: available_from < sample_date
    ).set_index("_row").reindex(np.arange(len(df)))

    out = df.copy()
    n = merged["cum_n"].fillna(0).to_numpy()
    pos = merged["cum_pos"].fillna(0).to_numpy()
    out["est_prior_samples"] = n
    out["est_prior_positives"] = pos
    out["est_prior_rate_smoothed"] = (pos + smoothing * prior_rate) / (n + smoothing)
    out["est_days_since_prior"] = (left[SAMPLE_DATE] - merged["_prior_date"]).dt.days.to_numpy()
    return out


def make_features(df: pd.DataFrame, daily: pd.DataFrame | None, cfg: dict, prior_rate: float) -> pd.DataFrame:
    """Return the model input frame (no target, no identifiers). daily=None disables history features."""
    X = pd.DataFrame(index=df.index)
    X[PRODUCT_CATEGORY] = df[PRODUCT_CATEGORY].fillna(UNKNOWN_CATEGORY).astype(str)
    X["sample_month"] = df[SAMPLE_DATE].dt.month.astype("Int64").astype(str).replace("<NA>", UNKNOWN_CATEGORY)
    cats, nums = meta_columns(df)
    for c in cats:
        X[c] = df[c].fillna(UNKNOWN_CATEGORY).astype(str)
    for c in nums:
        X[c] = pd.to_numeric(df[c], errors="coerce")
    if daily is not None:
        f = cfg["features"]
        hist = add_history_features(df, daily, f["label_lag_days"], prior_rate, f["history_smoothing"])
        for c in HISTORY_FEATURES:
            X[c] = hist[c].to_numpy()
    return X


def split_feature_types(X: pd.DataFrame) -> tuple[list[str], list[str]]:
    cat = [c for c in X.columns if not pd.api.types.is_numeric_dtype(X[c])]
    return cat, [c for c in X.columns if c not in cat]


def build_preprocessor(cat: list[str], num: list[str], min_category_count: int) -> ColumnTransformer:
    return ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=min_category_count,
                              sparse_output=False), cat),
        ("num", Pipeline([("impute", SimpleImputer(strategy="median", add_indicator=True)),
                          ("scale", StandardScaler())]), num),
    ])
