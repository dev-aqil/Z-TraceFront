import numpy as np
import pandas as pd
import pytest

from src.data.loader import apply_mapping
from src.features.build import HISTORY_FEATURES, add_history_features, build_daily_history, make_features
from src.features.leakage import LeakageError, assert_disjoint_splits, assert_no_leaky_features
from tests.test_loading import MAPPING, RAW


@pytest.mark.parametrize("name", ["Salmonella_Result", "serotype", "Campylobacter", "recall_status",
                                  "AMR_profile", "pfge_pattern", "salmonella_positive", "not_analyzed",
                                  "campylobacter_analysis_30ml_canceled", "aerobic_plate_count_mpn_ml",
                                  "enterobacteriaceae_mpn_ml", "allele_code"])
def test_denylist_blocks_target_derived_names(name):
    with pytest.raises(LeakageError):
        assert_no_leaky_features(["product_category", name])


def test_history_features_are_explicitly_allowed():
    assert_no_leaky_features(["product_category", *HISTORY_FEATURES], allowed=HISTORY_FEATURES)


def test_mapping_rejects_leaky_extra_feature():
    m = {**MAPPING, "features": {"extra": {"fake_salm": "categorical"}}}
    with pytest.raises(LeakageError):
        apply_mapping(RAW, m)


def test_features_exclude_target_and_identifiers(synthetic_df, cfg):
    X = make_features(synthetic_df, build_daily_history(synthetic_df), cfg, prior_rate=0.1)
    assert not {"salmonella_positive", "sample_id", "establishment_id", "sample_date"} & set(X.columns)


def _brute_force(df, lag):
    n, pos = [], []
    for _, r in df.iterrows():
        prior = df[(df["establishment_id"] == r["establishment_id"])
                   & (df["sample_date"] + pd.Timedelta(days=lag) < r["sample_date"])]
        n.append(len(prior))
        pos.append(int(prior["salmonella_positive"].sum()))
    return np.array(n), np.array(pos)


@pytest.mark.parametrize("lag", [0, 7])
def test_history_uses_only_strictly_earlier_reported_results(synthetic_df, lag):
    df = synthetic_df.head(400)
    out = add_history_features(df, build_daily_history(df), lag, prior_rate=0.1, smoothing=20)
    n, pos = _brute_force(df, lag)
    np.testing.assert_array_equal(out["est_prior_samples"], n)
    np.testing.assert_array_equal(out["est_prior_positives"], pos)


def test_own_and_same_day_labels_do_not_change_features(synthetic_df):
    df = synthetic_df.head(400).copy()
    base = add_history_features(df, build_daily_history(df), 0, 0.1, 20)
    i = 200
    flipped = df.copy()
    same_day = (flipped["sample_date"] >= df["sample_date"].iloc[i])  # this sample, same-day and later ones
    flipped.loc[same_day, "salmonella_positive"] = 1 - flipped.loc[same_day, "salmonella_positive"]
    after = add_history_features(flipped, build_daily_history(flipped), 0, 0.1, 20)
    rows = df.index[df["sample_date"] == df["sample_date"].iloc[i]]
    pd.testing.assert_frame_equal(base.loc[rows, list(HISTORY_FEATURES)], after.loc[rows, list(HISTORY_FEATURES)])


def test_disjoint_split_check_catches_overlap(synthetic_df):
    a, b = synthetic_df.iloc[:100], synthetic_df.iloc[90:200]
    with pytest.raises(LeakageError):
        assert_disjoint_splits({"train": a, "test": b}, temporal=False)
