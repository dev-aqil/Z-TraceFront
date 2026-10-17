"""Portable CSV contracts, validation and auditable row accounting."""

from __future__ import annotations

from collections import Counter
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator

NULL = r"\N"


def text(value: Any) -> str | None:
    """Only empty/whitespace/null are missing. Do not guess at N/A codes."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("expected a source string")
    return value.strip() or None


def number(value: Any, *, integer: bool = False, minimum: str | None = None) -> str | None:
    value = text(value)
    if value is None:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("not a decimal number") from error
    if not parsed.is_finite() or (minimum is not None and parsed < Decimal(minimum)):
        raise ValueError("nonfinite or below permitted minimum")
    if integer and parsed != parsed.to_integral_value():
        raise ValueError("not an integer")
    return str(int(parsed)) if integer else format(parsed, "f")


def identifier(value: Any) -> str:
    value = text(value)
    if value is None or not re.fullmatch(r"[0-9]+", value) or int(value) <= 0:
        raise ValueError("missing or invalid positive numeric identifier")
    return value  # retain leading zeros; release-local ID is not a predictor


def parse_date(value: Any, fmt: str, cutoff: date, minimum_year: int = 1900) -> str | None:
    value = text(value)
    if value is None:
        return None
    pattern = r"[0-9]{8}" if fmt == "%Y%m%d" else r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
    if not re.fullmatch(pattern, value):
        raise ValueError("invalid date format")
    parsed = datetime.strptime(value, fmt).date()
    if parsed.year < minimum_year or parsed > cutoff:
        raise ValueError("date outside documented plausibility window")
    return parsed.isoformat()


def encode(value: Any) -> str:
    if value is None:
        return NULL
    value = str(value)
    return "\\" + value if value.startswith("\\") else value


def read_table(path: Path) -> Iterator[dict[str, Any]]:
    """Read a clean CSV with its declared types; no dataframe dependency."""
    schema = json.loads(path.with_suffix(".schema.json").read_text())
    conversions = {"string": str, "json": json.loads, "integer": int,
                   "decimal": Decimal, "date": date.fromisoformat}
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(schema["columns"]):
            raise ValueError("CSV/schema column order mismatch")
        for row in reader:
            if set(row) != set(schema["columns"]) or any(not isinstance(v, str) for v in row.values()):
                raise ValueError("malformed clean CSV row width")
            parsed = {}
            for name, value in row.items():
                if value is None:
                    raise ValueError("malformed clean CSV")
                parsed[name] = (None if value == NULL else conversions[schema["columns"][name]["datatype"]](
                    value[1:] if value.startswith("\\\\") else value))
            yield parsed


class Duplicates:
    """Disk-backed exact-row detection for millions of analytical records."""

    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.execute("CREATE TABLE seen (digest BLOB PRIMARY KEY, source_row INTEGER) WITHOUT ROWID")
        self.connection.execute("BEGIN")

    def previous(self, raw: Any, source_row: int) -> int | None:
        digest = hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False,
                                          separators=(",", ":")).encode()).digest()
        result = self.connection.execute("SELECT source_row FROM seen WHERE digest=?", (digest,)).fetchone()
        if result:
            return result[0]
        self.connection.execute("INSERT INTO seen VALUES (?, ?)", (digest, source_row))
        return None

    def close(self) -> None:
        self.connection.close()


class Table:
    """One output table with explicit input/accepted/rejected row accounting."""

    def __init__(self, directory: Path, name: str, columns: dict[str, dict], *, grain: str,
                 source: dict, transformations: list[str], missing_semantics: list[str]):
        directory.mkdir(parents=True, exist_ok=True)
        self.name = name
        self.columns = {"source_row_number": {"datatype": "integer", "role": "lineage"}, **columns}
        self.path = directory / (name + ".csv")
        self.files = [self.path.open("w", encoding="utf-8", newline=""),
                      (directory / (name + ".rejected.jsonl")).open("w", encoding="utf-8"),
                      (directory / (name + ".issues.jsonl")).open("w", encoding="utf-8")]
        self.writer = csv.writer(self.files[0], lineterminator="\n")
        self.writer.writerow(self.columns)
        self.stats = {"raw_rows": 0, "clean_rows": 0, "rejected_rows": 0, "duplicate_rows": 0,
                      "malformed_rows": 0, "missing_critical_identifiers": 0, "invalid_numeric_rows": 0,
                      "invalid_date_rows": 0}
        self.before: Counter[str] = Counter()
        self.after: Counter[str] = Counter()
        self.reasons: Counter[str] = Counter()
        self.notes: Counter[str] = Counter()
        self.source = source
        self.schema = {"status": "NOT MODEL-READY", "table": name, "row_granularity": grain,
                       "source": source, "columns": self.columns,
                       "null_encoding": {"null": NULL, "empty_string": "non-null empty string",
                                         "escape": "Prefix an extra backslash to every non-null value starting with a backslash"},
                       "transformations": transformations, "missingness_semantics": missing_semantics,
                       "not_performed": ["ML imputation", "predictive features", "cross-source joins",
                                         "contamination/exceedance label creation", "model training"]}

    def observe(self, raw: dict[str, Any]) -> None:
        self.stats["raw_rows"] += 1
        self.before.update(k for k, v in raw.items() if v is None or isinstance(v, str) and not v.strip())

    def issue(self, row: int, code: str, field: str | None = None, raw_value: Any = None) -> None:
        self.notes[code] += 1
        self.files[2].write(json.dumps({"source_row_number": row, "reason_code": code,
                                       "field": field, "raw_value": raw_value}, sort_keys=True, ensure_ascii=False) + "\n")

    def reject(self, row: int, raw: Any, codes: list[str], row_identifier: str | None = None) -> None:
        codes = sorted(set(codes))
        self.stats["rejected_rows"] += 1
        self.reasons.update(codes)
        if isinstance(raw, dict) and None in raw:
            raw = {"csv_fields_including_extra_values": [[k, v] for k, v in raw.items()]}
        self.files[1].write(json.dumps({"source_row_number": row, "row_identifier": row_identifier,
                                       "reason_codes": codes, "raw_values": raw}, sort_keys=True, ensure_ascii=False) + "\n")

    def accept(self, row: int, values: dict[str, Any]) -> None:
        record = {"source_row_number": row, **values}
        if set(record) != set(self.columns):
            raise ValueError(f"{self.name}: output/schema fields differ: {set(record) ^ set(self.columns)}")
        self.stats["clean_rows"] += 1
        self.after.update(k for k, v in record.items() if v is None)
        self.writer.writerow(encode(record[k]) for k in self.columns)

    def close(self) -> dict:
        for stream in self.files:
            stream.close()
        self.path.with_suffix(".schema.json").write_text(json.dumps(self.schema, indent=2, ensure_ascii=False) + "\n")
        if self.stats["raw_rows"] != self.stats["clean_rows"] + self.stats["rejected_rows"]:
            raise ValueError(f"{self.name}: input row accounting failed")
        return {**self.stats, "table": self.name, "row_granularity": self.schema["row_granularity"],
                "missingness_before": dict(sorted(self.before.items())),
                "missingness_after": dict(sorted(self.after.items())),
                "missingness_denominators": {"before": "raw_rows", "after": "clean_rows"},
                "rejection_reasons": dict(sorted(self.reasons.items())),
                "quality_issue_counts": dict(sorted(self.notes.items())),
                "transformations": self.schema["transformations"],
                "missingness_semantics": self.schema["missingness_semantics"],
                "not_performed": self.schema["not_performed"]}


def string_columns(names: list[str]) -> dict[str, dict]:
    return {name: {"datatype": "string", "nullable": True} for name in names}


def conflicts(rows: list[dict], keys: list[str]) -> set[tuple]:
    """Quarantine all conflicting natural-key versions, never choose a winner."""
    first = {}
    bad = set()
    for raw in rows:
        key = tuple(text(raw.get(k)) for k in keys)
        if key in first and first[key] != raw:
            bad.add(key)
        first.setdefault(key, raw)
    return bad
