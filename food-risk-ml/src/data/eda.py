"""Exploratory analysis of the canonical dataset. Writes CSV tables, plots and a markdown summary."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.data.contract import (  # noqa: E402
    ESTABLISHMENT_ID,
    PRODUCT_CATEGORY,
    SAMPLE_DATE,
    SAMPLE_ID,
    SYNTHETIC_ID_PREFIX,
    TARGET,
)


def run_eda(df: pd.DataFrame, out_dir: str | Path) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    labelled = df[df[TARGET].notna()].copy()
    labelled[TARGET] = labelled[TARGET].astype(int)

    monthly = (labelled.dropna(subset=[SAMPLE_DATE])
               .groupby(labelled[SAMPLE_DATE].dt.to_period("M"))[TARGET].agg(n="size", positives="sum"))
    monthly["positive_rate"] = monthly["positives"] / monthly["n"]
    monthly.to_csv(out / "positive_rate_by_month.csv")

    by_cat = labelled.groupby(PRODUCT_CATEGORY)[TARGET].agg(n="size", positives="sum").sort_values("n", ascending=False)
    by_cat["positive_rate"] = by_cat["positives"] / by_cat["n"]
    by_cat.to_csv(out / "positive_rate_by_product_category.csv")

    est_counts = df[ESTABLISHMENT_ID].value_counts() if df[ESTABLISHMENT_ID].notna().any() else pd.Series(dtype=int)
    df.isna().mean().rename("missing_fraction").to_csv(out / "missingness.csv")

    if len(monthly):
        fig, ax = plt.subplots(figsize=(10, 4))
        monthly["positive_rate"].plot(ax=ax, marker=".")
        ax.set_ylabel("sample positive rate")
        ax.set_title("Salmonella sample positive rate by collection month")
        fig.tight_layout()
        fig.savefig(out / "positive_rate_by_month.png", dpi=120)
        plt.close(fig)

    summary = {
        "synthetic": bool(df[SAMPLE_ID].astype(str).str.startswith(SYNTHETIC_ID_PREFIX).any()),
        "n_rows": len(df),
        "n_labelled": len(labelled),
        "n_unlabelled": int(df[TARGET].isna().sum()),
        "positive_rate": float(labelled[TARGET].mean()) if len(labelled) else None,
        "date_min": str(df[SAMPLE_DATE].min()), "date_max": str(df[SAMPLE_DATE].max()),
        "missing_date_fraction": float(df[SAMPLE_DATE].isna().mean()),
        "n_product_categories": int(df[PRODUCT_CATEGORY].nunique()),
        "n_establishments": int(est_counts.size),
        "samples_per_establishment_median": float(est_counts.median()) if len(est_counts) else None,
    }
    lines = ["# EDA summary", ""]
    if summary["synthetic"]:
        lines += ["**SYNTHETIC DATA: these numbers describe a test fixture, not FSIS data.**", ""]
    lines += [f"- {k}: {v}" for k, v in summary.items()]
    lines += ["", "## Positive rate by product category (top 30 by n)", "", "```", by_cat.head(30).to_string(), "```"]
    (out / "eda_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary
