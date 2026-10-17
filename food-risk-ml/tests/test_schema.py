import pandas as pd
import pytest

from src.data.contract import SchemaError, validate_canonical


def test_synthetic_fixture_is_valid(synthetic_df):
    validate_canonical(synthetic_df)


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d.drop(columns="salmonella_positive"), "missing required"),
    (lambda d: d.assign(salmonella_positive=pd.array([2] * len(d), dtype="Int8")), "must be 0, 1"),
    (lambda d: d.assign(sample_id="dup"), "duplicated"),
    (lambda d: d.assign(sample_date=d["sample_date"].astype(str)), "not a datetime"),
    (lambda d: d.assign(sample_date=pd.Timestamp.now() + pd.Timedelta(days=30)), "future"),
    (lambda d: d.assign(product_category=None), "product_category"),
    (lambda d: d.assign(serotype="x"), "unexpected columns"),
    (lambda d: d.assign(meta_num_x="text"), "must be numeric"),
    (lambda d: d.assign(salmonella_positive=pd.array([pd.NA] * len(d), dtype="Int8")), "no labelled rows"),
])
def test_invalid_schema_rejected(synthetic_df, mutate, message):
    with pytest.raises(SchemaError, match=message):
        validate_canonical(mutate(synthetic_df))
