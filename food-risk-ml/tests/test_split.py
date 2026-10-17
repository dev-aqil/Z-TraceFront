import numpy as np
import pandas as pd

from src.features.split import make_split


def test_temporal_split_is_ordered_disjoint_and_date_aligned(synthetic_df, cfg):
    s = make_split(synthetic_df, cfg, seed=1)
    assert s.method == "temporal"
    assert s.train["sample_date"].max() < s.val["sample_date"].min()
    assert s.val["sample_date"].max() < s.test["sample_date"].min()
    dates = [set(p["sample_date"]) for p in s.parts().values()]
    assert not (dates[0] & dates[1]) and not (dates[1] & dates[2])  # no day straddles splits
    assert sum(len(p) for p in s.parts().values()) == len(synthetic_df)
    assert 0.6 < len(s.train) / len(synthetic_df) < 0.8


def test_split_is_reproducible(synthetic_df, cfg):
    a, b = make_split(synthetic_df, cfg, seed=1), make_split(synthetic_df, cfg, seed=1)
    for k in ("train", "val", "test"):
        assert a.parts()[k]["sample_id"].tolist() == b.parts()[k]["sample_id"].tolist()


def test_fallback_group_split_when_dates_unreliable(synthetic_df, cfg):
    df = synthetic_df.copy()
    df.loc[np.arange(len(df)) % 3 == 0, "sample_date"] = pd.NaT  # ~33% missing > 5% limit
    s = make_split(df, cfg, seed=1)
    assert s.method == "group_establishment"
    ests = [set(p["establishment_id"]) for p in s.parts().values()]
    assert not (ests[0] & ests[1]) and not (ests[0] & ests[2]) and not (ests[1] & ests[2])
