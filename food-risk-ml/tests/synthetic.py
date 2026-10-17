"""SYNTHETIC TEST FIXTURE. NOT FSIS DATA.

Generates a small fake dataset in the canonical schema so the code can be tested before real data exists.
Every sample_id starts with "SYNTH-"; the training pipeline detects this and flags all outputs as synthetic.
Numbers produced from this data are code checks, never evaluation results.
"""

import numpy as np
import pandas as pd

from src.data.contract import SYNTHETIC_ID_PREFIX


def make_synthetic_canonical(n: int = 2400, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    est = rng.integers(0, 40, n)
    est_rate = rng.uniform(0.02, 0.35, 40)[est]
    cats = np.array(["synthetic_parts", "synthetic_ground", "synthetic_carcass"])
    cat_idx = rng.integers(0, 3, n)
    dates = pd.Timestamp("2021-01-01") + pd.to_timedelta(np.sort(rng.integers(0, 3 * 365, n)), unit="D")
    season = 0.05 * np.sin(2 * np.pi * dates.dayofyear.to_numpy() / 365)
    p = np.clip(est_rate + np.array([0.0, 0.08, -0.02])[cat_idx] + season, 0.01, 0.95)
    return pd.DataFrame({
        "sample_id": [f"{SYNTHETIC_ID_PREFIX}{i:06d}" for i in range(n)],
        "sample_date": dates,
        "establishment_id": [f"SYNTH-EST-{e:03d}" for e in est],
        "product_category": cats[cat_idx],
        "meta_num_synthetic_score": rng.normal(size=n),
        "salmonella_positive": pd.array(rng.binomial(1, p), dtype="Int8"),
    })
