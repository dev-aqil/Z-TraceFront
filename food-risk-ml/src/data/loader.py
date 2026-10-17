"""Read locally supplied FSIS files, map them to the canonical schema, deduplicate and validate."""

import io
import json
import logging
import re
import tomllib
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.contract import (
    ALIASES,
    ESTABLISHMENT_ID,
    GENERIC_TARGET,
    META_CAT_PREFIX,
    META_NUM_PREFIX,
    PATHOGEN_COLUMN,
    PRODUCT_CATEGORY,
    SAMPLE_DATE,
    SAMPLE_ID,
    TARGET,
    UNKNOWN_CATEGORY,
    SchemaError,
    validate_canonical,
)
from src.features.leakage import assert_no_leaky_features

log = logging.getLogger(__name__)
DATA_SUFFIXES = (".csv", ".json", ".xlsx")


class MappingIncompleteError(RuntimeError):
    pass


def _is_fsis_lab_sampling(obj: Any) -> bool:
    return (isinstance(obj, list) and len(obj) == 1 and isinstance(obj[0], dict)
            and isinstance(obj[0].get("data"), dict) and "primary_table_data" in obj[0]["data"])


def _read_bytes(name: str, data: bytes) -> pd.DataFrame:
    suffix = Path(name).suffix.lower()
    if suffix == ".csv":
        # Everything as text; only empty cells are missing, so codes like "N/A" or "00123" survive untouched.
        return pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False, na_values=[""])
    if suffix == ".xlsx":
        return pd.read_excel(io.BytesIO(data), dtype=str)
    if suffix == ".json":
        obj = json.loads(data)
        if _is_fsis_lab_sampling(obj):
            # FSIS Lab Sampling data product: [{"metadata", "data": {primary_table_data, secondary_table_data},
            # "appendix"}]. Only the primary table is read. Secondary tests (serotype, allele code, PFGE/WGS, AMR)
            # exist only because a primary test was positive, so they are outcome-derived and never loaded.
            rows = obj[0]["data"]["primary_table_data"]
            log.info("%s: FSIS data product, reading %d primary rows (secondary table deliberately ignored)",
                     name, len(rows))
            return pd.DataFrame(rows).astype(str)
        if isinstance(obj, dict):
            lists = {k: v for k, v in obj.items() if isinstance(v, list) and v and isinstance(v[0], dict)}
            if len(lists) != 1:
                raise ValueError(f"{name}: JSON object with keys {list(obj)[:20]}; expected exactly one list of "
                                 "records. Inspect the structure and convert it to CSV.")
            obj = next(iter(lists.values()))
        if not isinstance(obj, list):
            raise ValueError(f"{name}: unsupported JSON top-level type {type(obj).__name__}")
        df = pd.json_normalize(obj)
        return df.astype("string").astype(object).where(df.notna(), None)
    raise ValueError(f"{name}: unsupported file type {suffix} (supported: {DATA_SUFFIXES} or .zip)")


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            members = [m for m in zf.namelist() if m.lower().endswith(DATA_SUFFIXES)]
            if len(members) != 1:
                raise ValueError(f"{path}: expected one data file in the zip, found {members}. Extract it first.")
            return _read_bytes(members[0], zf.read(members[0]))
    return _read_bytes(path.name, path.read_bytes())


def load_mapping(path: str | Path) -> dict[str, Any]:
    with open(path, "rb") as f:
        return tomllib.load(f)


def mapping_problems(m: dict[str, Any]) -> list[str]:
    cols, labels = m.get("columns", {}), m.get("labels", {})
    problems = [f"columns.{k} is empty" for k in ("sample_date", "salmonella_result") if not cols.get(k)]
    if not labels.get("positive_values"):
        problems.append("labels.positive_values is empty")
    if not labels.get("negative_values"):
        problems.append("labels.negative_values is empty")
    pos = {str(v).strip().casefold() for v in labels.get("positive_values", [])}
    neg = {str(v).strip().casefold() for v in labels.get("negative_values", [])}
    if pos & neg:
        problems.append(f"values listed as both positive and negative: {sorted(pos & neg)}")
    if not m.get("verified_by") or not m.get("verified_against"):
        problems.append("verified_by / verified_against not set (record who checked the official metadata)")
    return problems


def _snake(name: str) -> str:
    return re.sub(r"\W+", "_", name).strip("_").lower()


def apply_mapping(raw: pd.DataFrame, m: dict[str, Any]) -> pd.DataFrame:
    problems = mapping_problems(m)
    if problems:
        raise MappingIncompleteError("source mapping is incomplete, training is blocked:\n  - " + "\n  - ".join(problems))
    cols, extra = m["columns"], m.get("features", {}).get("extra", {})
    needed = [v for v in cols.values() if v] + list(extra)
    absent = [c for c in needed if c not in raw.columns]
    if absent:
        raise MappingIncompleteError(f"mapped source columns not found in file: {absent}")
    assert_no_leaky_features(list(extra))
    missing_tokens = {str(v).strip() for v in m.get("missing", {}).get("values", [])} | {""}

    def text(col: str) -> pd.Series:
        s = raw[col].astype("string").str.strip()
        return s.mask(s.isin(missing_tokens))

    out = pd.DataFrame(index=raw.index)
    if cols.get("sample_id"):
        out[SAMPLE_ID] = text(cols["sample_id"])
    else:
        log.warning("no sample_id column mapped: deriving ids from a hash of each full source row")
        out[SAMPLE_ID] = "row-" + pd.util.hash_pandas_object(raw, index=False).astype(str)

    date_text = text(cols["sample_date"])
    out[SAMPLE_DATE] = pd.to_datetime(date_text, format=m.get("dates", {}).get("format") or "ISO8601", errors="coerce")
    unparsed = date_text.notna() & out[SAMPLE_DATE].isna()
    if unparsed.any():
        log.warning("%d non-empty sample_date values failed to parse, e.g. %s",
                    unparsed.sum(), date_text[unparsed].unique()[:5].tolist())

    out[ESTABLISHMENT_ID] = text(cols["establishment_id"]) if cols.get("establishment_id") else pd.NA
    out[PRODUCT_CATEGORY] = (text(cols["product_category"]).fillna(UNKNOWN_CATEGORY)
                             if cols.get("product_category") else UNKNOWN_CATEGORY)

    result = text(cols["salmonella_result"]).str.casefold()
    pos = {str(v).strip().casefold() for v in m["labels"]["positive_values"]}
    neg = {str(v).strip().casefold() for v in m["labels"]["negative_values"]}
    out[TARGET] = pd.Series(pd.NA, index=raw.index, dtype="Int8")
    out.loc[result.isin(pos), TARGET] = 1
    out.loc[result.isin(neg), TARGET] = 0
    unmapped = result[out[TARGET].isna()]
    if len(unmapped):
        log.warning("%d rows have a result value in neither label list (excluded from training): %s",
                    len(unmapped), unmapped.value_counts(dropna=False).head(10).to_dict())

    for col, kind in extra.items():
        if kind == "numeric":
            out[META_NUM_PREFIX + _snake(col)] = pd.to_numeric(text(col), errors="coerce")
        elif kind == "categorical":
            out[META_CAT_PREFIX + _snake(col)] = text(col).fillna(UNKNOWN_CATEGORY).astype(object)
        else:
            raise MappingIncompleteError(f"features.extra.{col} must be 'categorical' or 'numeric', got {kind!r}")
    return out


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Drop exact duplicate rows; drop every copy of a sample_id whose copies disagree."""
    before = len(df)
    df = df.drop_duplicates()
    conflicting = df[SAMPLE_ID].duplicated(keep=False)
    if conflicting.any():
        log.warning("dropping %d rows: %d sample_ids with conflicting records",
                    conflicting.sum(), df.loc[conflicting, SAMPLE_ID].nunique())
        df = df[~conflicting]
    log.info("deduplication: %d -> %d rows", before, len(df))
    return df.reset_index(drop=True)


def read_tables(paths: list[str | Path]) -> pd.DataFrame:
    """Read and stack several files of the same dataset (e.g. FSIS current + archived fiscal years).
    Files must have identical columns; differing layouts need their own mapping, so they are rejected."""
    frames = [read_table(p) for p in paths]
    for p, f in zip(paths, frames, strict=True):
        log.info("read %d rows x %d columns from %s", *f.shape, p)
        if set(f.columns) != set(frames[0].columns):
            raise ValueError(f"{p} columns differ from {paths[0]}: "
                             f"{sorted(set(f.columns) ^ set(frames[0].columns))}. Map these files separately.")
    return pd.concat(frames, ignore_index=True)


def load_fsis(raw_paths: list[str | Path], mapping_path: str | Path) -> pd.DataFrame:
    return validate_canonical(deduplicate(apply_mapping(read_tables(raw_paths), load_mapping(mapping_path))))


def resolve_aliases(df: pd.DataFrame, pathogen: str = "Salmonella") -> pd.DataFrame:
    """Accept Person A's project-wide names. A generic pathogen_positive label is only accepted together with
    a pathogen column, and only that pathogen's rows are kept: other pathogens are separate targets."""
    clashes = [a for a, c in ALIASES.items() if a in df and c in df]
    if clashes:
        raise SchemaError([f"both {a!r} and {ALIASES[a]!r} present; deliver one" for a in clashes])
    df = df.rename(columns={a: c for a, c in ALIASES.items() if a in df})
    if GENERIC_TARGET in df:
        if TARGET in df or PATHOGEN_COLUMN not in df:
            raise SchemaError([f"{GENERIC_TARGET} needs a {PATHOGEN_COLUMN!r} column and no {TARGET!r} column"])
        keep = df[PATHOGEN_COLUMN].astype(str).str.strip().str.casefold() == pathogen.casefold()
        log.info("keeping %d/%d rows where %s == %s", keep.sum(), len(df), PATHOGEN_COLUMN, pathogen)
        df = df[keep].drop(columns=PATHOGEN_COLUMN).rename(columns={GENERIC_TARGET: TARGET})
    return df


def load_canonical(path: str | Path, pathogen: str = "Salmonella") -> pd.DataFrame:
    """Load a canonical CSV (written by `prepare` or delivered by Person A) and validate it."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    df = resolve_aliases(df, pathogen)
    if SAMPLE_DATE in df:
        df[SAMPLE_DATE] = pd.to_datetime(df[SAMPLE_DATE], format="ISO8601", errors="coerce")
    if TARGET in df:
        # Only exact "0"/"1" are labels; anything else is left as text so validation reports it.
        if df[TARGET].dropna().isin(["0", "1"]).all():
            df[TARGET] = pd.to_numeric(df[TARGET]).astype("Int8")
    for c in df.columns:
        if c.startswith(META_NUM_PREFIX):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return validate_canonical(df.reset_index(drop=True))
