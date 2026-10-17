from src.data.eda import run_eda


def test_eda_writes_outputs_and_flags_synthetic(synthetic_df, tmp_path):
    s = run_eda(synthetic_df, tmp_path)
    assert s["synthetic"] is True and s["n_labelled"] == len(synthetic_df)
    assert "SYNTHETIC" in (tmp_path / "eda_summary.md").read_text()
    for f in ("positive_rate_by_month.csv", "positive_rate_by_product_category.csv", "missingness.csv"):
        assert (tmp_path / f).exists()
