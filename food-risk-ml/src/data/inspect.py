"""Schema inspection for a locally supplied raw file: what columns exist and what their values look like.

Output is evidence for filling configs/source_mapping.toml. Candidate columns are keyword hints only; the
official FSIS metadata decides the mapping.
"""

import json
from pathlib import Path

import pandas as pd

from src.data.loader import read_table
from src.features.leakage import leakage_hits

HINTS = {
    "sample_id": ("sample", "form", "number", "_id", "id"),
    "sample_date": ("date", "collect"),
    "establishment_id": ("establishment", "est", "plant"),
    "product_category": ("product", "project", "category", "class", "type"),
    "salmonella_result": ("salmonella", "salm"),
}
DATE_FORMATS = ("ISO8601", "%m/%d/%Y", "%d/%m/%Y", "%Y%m%d")


def profile(df: pd.DataFrame) -> list[dict]:
    rows = []
    for c in df.columns:
        s = df[c]
        text = s.dropna().astype(str).str.strip()
        sample = text.head(2000)
        date_rates = {f: float(pd.to_datetime(sample, format=f, errors="coerce").notna().mean()) if len(sample) else 0.0
                      for f in DATE_FORMATS}
        rows.append({
            "column": c,
            "n_missing": int(s.isna().sum() + (text == "").sum()),
            "n_unique": int(text.nunique()),
            "top_values": {str(k): int(v) for k, v in text.value_counts().head(10).items()},
            "date_parse_rate": {k: round(v, 3) for k, v in date_rates.items() if v > 0},
            "numeric_parse_rate": round(float(pd.to_numeric(sample, errors="coerce").notna().mean()), 3)
            if len(sample) else 0.0,
            "leakage_denylist_hit": bool(leakage_hits([c])),
        })
    return rows


def candidates(columns: list[str]) -> dict[str, list[str]]:
    return {field: [c for c in columns if any(k in c.lower() for k in keys)] for field, keys in HINTS.items()}


def inspect_file(path: str | Path, out_dir: str | Path) -> dict:
    df = read_table(path)
    report = {
        "file": str(path),
        "n_rows": len(df),
        "n_columns": df.shape[1],
        "n_exact_duplicate_rows": int(df.duplicated().sum()),
        "columns": profile(df),
        "candidate_columns_hint_only": candidates(list(df.columns)),
    }
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"schema_inspection_{Path(path).stem}.json").write_text(json.dumps(report, indent=2))

    lines = [
        f"# Schema inspection: `{Path(path).name}`", "",
        f"Rows: {report['n_rows']} | Columns: {report['n_columns']} | "
        f"Exact duplicate rows: {report['n_exact_duplicate_rows']}", "",
        "Candidate columns are keyword hints. Confirm each mapping against the official FSIS metadata.", "",
    ]
    for field, cols in report["candidate_columns_hint_only"].items():
        lines.append(f"- **{field}** hints: {', '.join(f'`{c}`' for c in cols) or '(none)'}")
    lines += ["", "| column | missing | unique | date parse | numeric | leakage denylist | top values |",
              "|---|---|---|---|---|---|---|"]
    for r in report["columns"]:
        top = "; ".join(f"{k} ({v})" for k, v in list(r["top_values"].items())[:5]).replace("|", "/")
        lines.append(f"| `{r['column']}` | {r['n_missing']} | {r['n_unique']} | {r['date_parse_rate'] or ''} | "
                     f"{r['numeric_parse_rate']} | {'YES' if r['leakage_denylist_hit'] else ''} | {top} |")
    (out / f"schema_inspection_{Path(path).stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
