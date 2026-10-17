"""Reproducible train/validation/test splitting: chronological by default, grouped fallback otherwise."""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from src.data.contract import ESTABLISHMENT_ID, SAMPLE_DATE, SAMPLE_ID, TARGET
from src.features.leakage import assert_disjoint_splits

log = logging.getLogger(__name__)


@dataclass
class Split:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame
    method: str  # "temporal" or "group_establishment"
    notes: str

    def parts(self) -> dict[str, pd.DataFrame]:
        return {"train": self.train, "val": self.val, "test": self.test}


def temporal_split(df: pd.DataFrame, train_frac: float, val_frac: float) -> Split:
    """Assign whole collection dates to splits in time order so no date straddles two splits."""
    dated = df.dropna(subset=[SAMPLE_DATE])
    dropped = len(df) - len(dated)
    counts = dated.groupby(SAMPLE_DATE).size().sort_index()
    start = (counts.cumsum() - counts) / counts.sum()  # fraction of rows before each date
    label = np.where(start < train_frac, "train", np.where(start < train_frac + val_frac, "val", "test"))
    which = dated[SAMPLE_DATE].map(pd.Series(label, index=counts.index))
    parts = {k: dated[which == k].reset_index(drop=True) for k in ("train", "val", "test")}
    notes = (f"chronological split on {SAMPLE_DATE}; {dropped} rows without a date excluded; "
             + "; ".join(f"{k}: {v[SAMPLE_DATE].min().date()}..{v[SAMPLE_DATE].max().date()}"
                         for k, v in parts.items() if len(v)))
    return Split(**parts, method="temporal", notes=notes)


def group_split(df: pd.DataFrame, train_frac: float, val_frac: float, seed: int) -> Split:
    """Fallback when dates are unreliable: whole establishments go to one split so correlated samples from
    one plant are never on both sides. Rows without an establishment are their own group."""
    groups = df[ESTABLISHMENT_ID].astype("string").fillna("sample:" + df[SAMPLE_ID].astype(str))
    test_frac = 1 - train_frac - val_frac
    rest_idx, test_idx = next(GroupShuffleSplit(1, test_size=test_frac, random_state=seed).split(df, groups=groups))
    rest = df.iloc[rest_idx]
    tr_idx, val_idx = next(GroupShuffleSplit(1, test_size=val_frac / (train_frac + val_frac), random_state=seed)
                           .split(rest, groups=groups.iloc[rest_idx]))
    return Split(rest.iloc[tr_idx].reset_index(drop=True), rest.iloc[val_idx].reset_index(drop=True),
                 df.iloc[test_idx].reset_index(drop=True), method="group_establishment",
                 notes="FALLBACK: dates unreliable; grouped random split by establishment_id (seeded). "
                       "Evaluation does not measure performance on future periods.")


def make_split(df: pd.DataFrame, cfg: dict, seed: int) -> Split:
    s = cfg["split"]
    labelled = df[df[TARGET].notna()]
    missing = labelled[SAMPLE_DATE].isna().mean()
    if missing <= s["max_missing_date_frac"]:
        split = temporal_split(labelled, s["train_frac"], s["val_frac"])
    else:
        log.warning("%.1f%% of labelled rows lack sample_date: using grouped fallback split", 100 * missing)
        split = group_split(labelled, s["train_frac"], s["val_frac"], seed)
    for name, part in split.parts().items():
        if len(part) == 0 or part[TARGET].nunique() < 2:
            raise ValueError(f"{name} split has {len(part)} rows and classes {sorted(part[TARGET].unique())}; "
                             "both classes are needed in every split")
    assert_disjoint_splits(split.parts(), temporal=split.method == "temporal")
    log.info("%s | sizes train=%d val=%d test=%d", split.notes, len(split.train), len(split.val), len(split.test))
    return split
