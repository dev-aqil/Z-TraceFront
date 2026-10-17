"""Leakage guards: target-derived / post-sampling feature names and split contamination."""

import pandas as pd

from src.data.contract import SAMPLE_DATE, SAMPLE_ID

# Case-insensitive substrings that indicate post-sampling or target-derived information. Conservative on
# purpose: a false positive blocks a feature (fixable by renaming after review); a false negative leaks.
DENYLIST = (
    "salmonella", "salm", "campylobacter", "campy", "listeria", "stec", "ecoli", "e_coli",
    "serotype", "serovar", "serogroup", "pfge", "wgs", "isolate", "amr", "resist",
    "result", "positive", "negative", "outcome", "finding", "detect", "mpn", "cfu",
    "recall", "enforcement", "followup", "follow_up", "status", "lab", "analys", "analyz", "cancel",
    "plate_count", "aerobic", "enterobacteriaceae", "quantitative", "allele", "fsis_number",
    "target", "label",
)


class LeakageError(ValueError):
    pass


def leakage_hits(names: list[str], allowed: tuple[str, ...] = ()) -> list[str]:
    return [n for n in names if n not in allowed and any(t in n.lower() for t in DENYLIST)]


def assert_no_leaky_features(names: list[str], allowed: tuple[str, ...] = ()) -> None:
    hits = leakage_hits(names, allowed)
    if hits:
        raise LeakageError(f"features look target-derived or post-sampling: {hits}")


def assert_disjoint_splits(splits: dict[str, pd.DataFrame], temporal: bool) -> None:
    """No sample in two splits; for temporal splits, every train date < val dates < test dates."""
    names = list(splits)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            overlap = set(splits[a][SAMPLE_ID]) & set(splits[b][SAMPLE_ID])
            if overlap:
                raise LeakageError(f"{len(overlap)} sample_ids appear in both {a} and {b}")
    if temporal:
        for a, b in zip(names, names[1:], strict=False):
            if splits[a][SAMPLE_DATE].max() >= splits[b][SAMPLE_DATE].min():
                raise LeakageError(f"temporal order violated between {a} and {b}")
