import json
import zipfile

import pandas as pd
import pytest

from src.data.loader import (
    MappingIncompleteError,
    apply_mapping,
    deduplicate,
    load_canonical,
    read_table,
    read_tables,
)

# Source column names below are invented for the fixture; they are NOT the real FSIS names.
RAW = pd.DataFrame({
    "fake_id": ["A1", "A2", "A3", "A4"],
    "fake_collected": ["2023-01-05", "2023-02-10", "not a date", "2023-03-01"],
    "fake_est": ["E1", "E1", "E2", ""],
    "fake_product": ["parts", "ground", "", "parts"],
    "fake_salm": ["POS", "neg ", "Not Tested", "NEG"],
})
MAPPING = {
    "verified_by": "test", "verified_against": "synthetic fixture",
    "columns": {"sample_id": "fake_id", "sample_date": "fake_collected", "establishment_id": "fake_est",
                "product_category": "fake_product", "pathogen_result": "fake_salm"},
    "dates": {"format": "%Y-%m-%d"},
    "labels": {"positive_values": ["pos"], "negative_values": ["NEG"]},
    "features": {"extra": {}},
}


def test_read_table_csv_keeps_codes_as_text(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("code,result\n00123,N/A\n,NEG\n")
    df = read_table(p)
    assert df["code"].iloc[0] == "00123"
    assert df["result"].iloc[0] == "N/A"  # only empty cells are missing
    assert pd.isna(df["code"].iloc[1])


def test_read_table_json_records_and_zip(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"meta": {"v": 1}, "records": [{"a": 1, "b": "x"}, {"a": 2}]}))
    assert len(read_table(tmp_path / "a.json")) == 2
    with zipfile.ZipFile(tmp_path / "a.zip", "w") as zf:
        zf.writestr("inner.csv", "a,b\n1,2\n")
    assert list(read_table(tmp_path / "a.zip").columns) == ["a", "b"]


def test_read_table_fsis_product_reads_primary_only(tmp_path):
    # Same structure as the FSIS Lab Sampling JSON product; values are invented.
    obj = [{"metadata": {"x": 1},
            "data": {"primary_table_data": [{"form_id": "1", "sample_number": 10, "res": "Negative"}],
                     "secondary_table_data": [{"form_id": "1", "serotype": "fake"}]},
            "appendix": []}]
    (tmp_path / "f.json").write_text(json.dumps(obj))
    df = read_table(tmp_path / "f.json")
    assert list(df.columns) == ["form_id", "sample_number", "res"] and df["sample_number"].iloc[0] == "10"


def test_missing_tokens_become_missing():
    raw = RAW.assign(fake_product=["NULL", "parts", "", "x"], fake_salm=["NULL", "POS", "NEG", "NEG"])
    out = apply_mapping(raw, {**MAPPING, "missing": {"values": ["NULL"]}})
    assert out["product_category"].iloc[0] == "__unknown__" and pd.isna(out["pathogen_positive"].iloc[0])


def test_read_table_rejects_ambiguous_json(tmp_path):
    (tmp_path / "b.json").write_text(json.dumps({"x": [{"a": 1}], "y": [{"b": 2}]}))
    with pytest.raises(ValueError, match="exactly one list"):
        read_table(tmp_path / "b.json")


def test_apply_mapping_labels_dates_and_unknowns():
    out = apply_mapping(RAW, MAPPING)
    assert out["pathogen_positive"].tolist()[:2] == [1, 0]
    assert pd.isna(out["pathogen_positive"].iloc[2])  # "Not Tested" is in neither list -> missing label
    assert pd.isna(out["sample_date"].iloc[2])
    assert out["product_category"].iloc[2] == "__unknown__"
    assert pd.isna(out["establishment_id"].iloc[3])


def test_unfilled_mapping_blocks_training():
    blank = {**MAPPING, "verified_by": "", "labels": {"positive_values": [], "negative_values": []}}
    with pytest.raises(MappingIncompleteError):
        apply_mapping(RAW, blank)


def test_mapping_rejects_missing_source_column():
    bad = {**MAPPING, "columns": {**MAPPING["columns"], "sample_date": "nope"}}
    with pytest.raises(MappingIncompleteError, match="not found"):
        apply_mapping(RAW, bad)


def test_read_tables_stacks_same_layout_and_rejects_different(tmp_path):
    (tmp_path / "fy1.csv").write_text("a,b\n1,2\n")
    (tmp_path / "fy2.csv").write_text("b,a\n3,4\n")
    (tmp_path / "other.csv").write_text("a,c\n1,2\n")
    assert len(read_tables([tmp_path / "fy1.csv", tmp_path / "fy2.csv"])) == 2
    with pytest.raises(ValueError, match="columns differ"):
        read_tables([tmp_path / "fy1.csv", tmp_path / "other.csv"])


def test_deduplicate_drops_conflicting_ids():
    df = pd.DataFrame({"sample_id": ["a", "a", "b", "b"], "pathogen_positive": [1, 0, 1, 1]})
    assert deduplicate(df)["sample_id"].tolist() == ["b"]


def test_load_canonical_accepts_person_a_flat_export(tmp_path):
    # Flat export shaped like configs/canonical_schema.json (repo root): observations joined with labels.
    p = tmp_path / "a.csv"
    pd.DataFrame({
        "observation_id": ["o1", "o2", "o3", "o4"], "dataset_id": ["fsis"] * 4, "prediction_time": ["x"] * 4,
        "sample_id": ["1", "2", "3", "4"],
        "sample_time": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04"],
        "factory_id": ["fsis:1", "fsis:1", "fsis:2", "fsis:2"], "sampling_program": ["HC_CH_CARC01", "", "F_CH_COM01", "X"],
        "food_category": ["chicken", "chicken", "", "turkey"], "is_synthetic": ["false"] * 4,
        "analyte": ["Salmonella", "Campylobacter", "salmonella", "Salmonella"],
        "pathogen_positive": ["true", "false", "false", ""],
        "label_status": ["observed", "observed", "observed", "untested"],
    }).to_csv(p, index=False)
    df = load_canonical(p)
    assert df["sample_id"].tolist() == ["1", "3", "4"]  # Campylobacter row is a different target, dropped
    assert df["pathogen_positive"].tolist()[:2] == [1, 0] and pd.isna(df["pathogen_positive"].iloc[2])
    assert df["product_category"].tolist() == ["HC_CH_CARC01", "F_CH_COM01", "X"]  # project code, not commodity
    assert df["meta_cat_food_category"].tolist() == ["chicken", "__unknown__", "turkey"]
    assert "observation_id" not in df and not df["is_synthetic"].any()


def test_config_selects_pathogen_sections_with_separate_outputs():
    from src.config import load_config
    s, c = load_config(), load_config(pathogen="campylobacter")
    assert (s["pathogen"], c["pathogen"]) == ("Salmonella", "Campylobacter")
    for k in ("mapping", "processed", "reports", "registry"):
        assert s["paths"][k] != c["paths"][k]  # models can never overwrite each other
    with pytest.raises(KeyError, match="unknown pathogen"):
        load_config(pathogen="norovirus")


def test_campylobacter_mapping_reads_enrichment_result_only():
    from src.config import load_config, resolve
    from src.data.loader import load_mapping
    m = load_mapping(resolve(load_config(pathogen="campylobacter")["paths"]["mapping"]))
    raw = pd.DataFrame({  # invented values, FSIS column names
        "form_id": ["1", "2", "3"], "collection_date": ["2024-01-01"] * 3, "establishment_id": ["9"] * 3,
        "project_code": ["HC_CH_CARC01"] * 3, "sample_source_name": ["x"] * 3, "product_type": ["NULL"] * 3,
        "establishment_state": ["GA"] * 3, "salmonella_sp_analysis": ["Positive", "Positive", "Negative"],
        "campylobacter_analysis_30ml": ["NEGATIVE", "Positive", "NULL"],
        "campylobacter_analysis_1ml": ["Positive", "NULL", "Positive"],
    })
    out = apply_mapping(raw, m)
    assert out["pathogen_positive"].tolist()[:2] == [0, 1]  # case-insensitive NEGATIVE; enrichment only
    assert pd.isna(out["pathogen_positive"].iloc[2])          # direct-plate-only row: no label
    assert not any("salmonella" in c or "campylobacter" in c for c in out.columns)
