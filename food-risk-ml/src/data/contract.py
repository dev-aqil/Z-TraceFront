"""Canonical internal schema shared with Person A. See docs/data_contract.md for the full definitions."""

import pandas as pd

SAMPLE_ID = "sample_id"
SAMPLE_DATE = "sample_date"
ESTABLISHMENT_ID = "establishment_id"
PRODUCT_CATEGORY = "product_category"
TARGET = "salmonella_positive"

IS_SYNTHETIC = "is_synthetic"

REQUIRED_COLUMNS = [SAMPLE_ID, SAMPLE_DATE, PRODUCT_CATEGORY, TARGET]
OPTIONAL_COLUMNS = [ESTABLISHMENT_ID, IS_SYNTHETIC]
UNKNOWN_CATEGORY = "__unknown__"
META_CAT_PREFIX = "meta_cat_"
META_NUM_PREFIX = "meta_num_"
SYNTHETIC_ID_PREFIX = "SYNTH-"  # rows whose sample_id starts with this are synthetic test fixtures
TASK = "biological_pathogen_positive"  # one of three separate problem types; see docs/data_contract.md

# Person A's configs/canonical_schema.json names -> this model's canonical names (docs/data_contract.md §7).
# The FSIS project code is Person A's sampling_program; their commodity-type fields become extra features.
ALIASES = {
    "sample_time": SAMPLE_DATE, "factory_id": ESTABLISHMENT_ID, "sampling_program": PRODUCT_CATEGORY,
    "food_category": META_CAT_PREFIX + "food_category", "commodity": META_CAT_PREFIX + "commodity",
    "food_type": META_CAT_PREFIX + "food_type", "state": META_CAT_PREFIX + "state",
}
PATHOGEN_COLUMNS = ("pathogen", "analyte")  # Person A uses analyte
GENERIC_TARGET, LABEL_STATUS = "pathogen_positive", "label_status"
# Person A lineage/label metadata: kept in their store, not model inputs, so dropped on load.
LINEAGE_COLUMNS = (
    "observation_id", "dataset_id", "dataset_version", "source_record_id", "prediction_time",
    "prediction_time_precision", "label_id", "target_name", "label_source_record_id", "label_definition_version",
    "assay_method", "result_available_at",
)


def is_synthetic(df: pd.DataFrame) -> bool:
    flagged = bool(df[IS_SYNTHETIC].fillna(False).astype(bool).any()) if IS_SYNTHETIC in df else False
    return flagged or bool(df[SAMPLE_ID].astype(str).str.startswith(SYNTHETIC_ID_PREFIX).any())


class SchemaError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("Canonical schema validation failed:\n  - " + "\n  - ".join(problems))


def meta_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    cats = [c for c in df.columns if c.startswith(META_CAT_PREFIX)]
    nums = [c for c in df.columns if c.startswith(META_NUM_PREFIX)]
    return cats, nums


def validate_canonical(df: pd.DataFrame, require_labels: bool = True) -> pd.DataFrame:
    """Raise SchemaError listing every contract violation; return df unchanged if valid."""
    problems: list[str] = []
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError([f"missing required columns: {missing}"])

    known = set(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
    unexpected = [c for c in df.columns if c not in known and not c.startswith((META_CAT_PREFIX, META_NUM_PREFIX))]
    if unexpected:
        problems.append(f"unexpected columns (extras must be prefixed meta_cat_/meta_num_): {unexpected}")

    ids = df[SAMPLE_ID]
    if ids.isna().any() or (ids.astype(str).str.strip() == "").any():
        problems.append("sample_id has missing values")
    if ids.duplicated().any():
        problems.append(f"sample_id has {int(ids.duplicated().sum())} duplicated values")

    if not pd.api.types.is_datetime64_any_dtype(df[SAMPLE_DATE]):
        problems.append("sample_date is not a datetime column (parse ISO-8601 dates first)")
    elif (df[SAMPLE_DATE] > pd.Timestamp.now() + pd.Timedelta(days=1)).any():
        problems.append("sample_date contains dates in the future")

    if df[PRODUCT_CATEGORY].isna().any():
        problems.append(f"product_category has missing values (use '{UNKNOWN_CATEGORY}')")

    bad = df[TARGET].dropna()
    bad = bad[~bad.isin([0, 1])]
    if len(bad):
        problems.append(f"salmonella_positive must be 0, 1 or missing; found {sorted(map(str, bad.unique()))[:10]}")
    if require_labels and df[TARGET].notna().sum() == 0:
        problems.append("no labelled rows (salmonella_positive is entirely missing)")

    if IS_SYNTHETIC in df and not pd.api.types.is_bool_dtype(df[IS_SYNTHETIC]):
        problems.append("is_synthetic must be boolean")

    _, nums = meta_columns(df)
    for c in nums:
        if not pd.api.types.is_numeric_dtype(df[c]):
            problems.append(f"{c} must be numeric")

    if problems:
        raise SchemaError(problems)
    return df
