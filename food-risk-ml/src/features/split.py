"""Reproducible train/validation/test splitting: chronological by default, grouped fallback otherwise."""

import logging
from dataclasses import dataclass

import pandas as pd

from src.data.contract import ESTABLISHMENT_ID, SAMPLE_DATE, TARGET
from src.evaluation import splits as generic
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
    parts = generic.temporal_split(df, SAMPLE_DATE, train_frac, val_frac)
    dropped = len(df) - sum(len(v) for v in parts.values())
    notes = (f"chronological split on {SAMPLE_DATE}; {dropped} rows without a date excluded; "
             + "; ".join(f"{k}: {v[SAMPLE_DATE].min().date()}..{v[SAMPLE_DATE].max().date()}"
                         for k, v in parts.items() if len(v)))
    return Split(**parts, method="temporal", notes=notes)


def group_split(df: pd.DataFrame, train_frac: float, val_frac: float, seed: int) -> Split:
    """Fallback when dates are unreliable: whole establishments go to one split so correlated samples from
    one plant are never on both sides. Rows without an establishment are their own group."""
    parts = generic.grouped_split(df, ESTABLISHMENT_ID, train_frac, val_frac, seed)
    return Split(**parts, method="group_establishment",
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
