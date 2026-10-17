"""Generic train/validation/test splits. Rationale per target: reports/modeling_split_strategy.md (repo root)."""

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit, train_test_split

PARTS = ("train", "val", "test")


class SplitError(ValueError):
    pass


def temporal_split(df: pd.DataFrame, time_col: str, train_frac: float, val_frac: float) -> dict[str, pd.DataFrame]:
    """Assign whole time units (rows sharing a timestamp) to splits in time order, so no instant straddles two
    splits. Rows without a time are excluded; callers decide whether that is acceptable."""
    dated = df.dropna(subset=[time_col])
    counts = dated.groupby(time_col).size().sort_index()
    start = (counts.cumsum() - counts) / counts.sum()  # fraction of rows before each time unit
    label = np.where(start < train_frac, "train", np.where(start < train_frac + val_frac, "val", "test"))
    which = dated[time_col].map(pd.Series(label, index=counts.index))
    return {k: dated[which == k].reset_index(drop=True) for k in PARTS}


def grouped_split(df: pd.DataFrame, group_col: str, train_frac: float, val_frac: float,
                  seed: int) -> dict[str, pd.DataFrame]:
    """Every group (facility, supplier, experiment) lands in exactly one split. Rows with no group are their own
    group, keyed by row position."""
    groups = df[group_col].astype("string").fillna("__row__" + pd.Series(np.arange(len(df)), index=df.index).astype(str))
    test_frac = 1 - train_frac - val_frac
    rest_idx, test_idx = next(GroupShuffleSplit(1, test_size=test_frac, random_state=seed).split(df, groups=groups))
    rest = df.iloc[rest_idx]
    tr, va = next(GroupShuffleSplit(1, test_size=val_frac / (train_frac + val_frac), random_state=seed)
                  .split(rest, groups=groups.iloc[rest_idx]))
    return {"train": rest.iloc[tr].reset_index(drop=True), "val": rest.iloc[va].reset_index(drop=True),
            "test": df.iloc[test_idx].reset_index(drop=True)}


def geographic_holdout(df: pd.DataFrame, region_col: str, test_regions: list[str], val_regions: list[str]
                       ) -> dict[str, pd.DataFrame]:
    """Named regions are held out entirely; measures transfer to unseen places, not future periods."""
    if set(test_regions) & set(val_regions):
        raise SplitError("a region cannot be in both validation and test")
    region = df[region_col].astype(str)
    return {"train": df[~region.isin(test_regions + val_regions)].reset_index(drop=True),
            "val": df[region.isin(val_regions)].reset_index(drop=True),
            "test": df[region.isin(test_regions)].reset_index(drop=True)}


def random_split(df: pd.DataFrame, target: str, train_frac: float, val_frac: float, seed: int,
                 allow_random: bool = False) -> dict[str, pd.DataFrame]:
    """Stratified random split. Refused unless the experiment explicitly allows it: random splits mix repeated
    facilities and periods across train and test and overstate performance for historical prediction."""
    if not allow_random:
        raise SplitError("random split refused: set allow_random only for a documented cross-sectional experiment")
    strat = df[target] if df[target].nunique() < 20 else None
    train, rest = train_test_split(df, train_size=train_frac, random_state=seed, stratify=strat)
    val, test = train_test_split(rest, train_size=val_frac / (1 - train_frac), random_state=seed,
                                 stratify=rest[target] if strat is not None else None)
    return {"train": train.reset_index(drop=True), "val": val.reset_index(drop=True), "test": test.reset_index(drop=True)}


def assert_split_integrity(parts: dict[str, pd.DataFrame], id_col: str | None = None, time_col: str | None = None,
                           group_col: str | None = None) -> None:
    """No row in two splits; optional chronology (train < val < test) and group-exclusivity checks."""
    names = [k for k in PARTS if k in parts]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if id_col and set(parts[a][id_col]) & set(parts[b][id_col]):
                raise SplitError(f"rows with the same {id_col} in {a} and {b}")
            if group_col:
                shared = set(parts[a][group_col].dropna()) & set(parts[b][group_col].dropna())
                if shared:
                    raise SplitError(f"{len(shared)} {group_col} values in both {a} and {b}")
    if time_col:
        for a, b in zip(names, names[1:], strict=False):
            if len(parts[a]) and len(parts[b]) and parts[a][time_col].max() >= parts[b][time_col].min():
                raise SplitError(f"chronology violated between {a} and {b}")
