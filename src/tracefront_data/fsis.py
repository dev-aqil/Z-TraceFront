"""Inspect an official FSIS JSON/CSV without cleaning or generating labels.

Current release field names and code vocabularies must be reviewed against the
matching dictionary. Neither blank nor an absent assay means a negative result.
"""

from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path
from typing import Any, Iterable


def json_pointer(value: Any, pointer: str) -> Any:
    """Resolve an explicit RFC 6901 pointer, including the root pointer ''."""
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise ValueError("records_pointer must be an RFC 6901 JSON pointer")
    for token in pointer[1:].split("/"):
        key = token.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def record_arrays(value: Any, pointer: str = "", depth: int = 0) -> list[str]:
    """Find candidate record collections; never guess between data and metadata."""
    if isinstance(value, list):
        return [pointer] if value and all(isinstance(row, dict) for row in value) else []
    if not isinstance(value, dict) or depth > 5:
        return []
    paths = []
    for key, child in value.items():
        escaped = key.replace("~", "~0").replace("/", "~1")
        paths.extend(record_arrays(child, pointer + "/" + escaped, depth + 1))
    return paths


def raw_token(value: Any) -> str:
    """Unambiguous raw-value count keys: JSON null, empty string and 'null' differ."""
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def profile_rows(rows: Iterable[dict[str, Any]], contract: dict[str, Any]) -> dict[str, Any]:
    identity_columns = contract.get("identity_columns", [])
    fields = contract.get("fields", {})
    filters = contract.get("cohort_filters", {})
    code_groups = contract.get("result_codes", {})
    reviewed = contract.get("mapping_reviewed", False)
    for group in ("positive", "negative"):
        if any(value is None or (isinstance(value, str) and not value.strip()) for value in code_groups.get(group, [])):
            raise ValueError("missing/blank results cannot be mapped to positive or negative")
    if reviewed and (not identity_columns or not filters or not fields.get("result") or not fields.get("collection_date")):
        raise ValueError("reviewed cohort needs identity columns, collection date, result and exact cohort filters")
    codes = [raw_token(code) for values in code_groups.values() for code in values]
    if len(codes) != len(set(codes)):
        raise ValueError("a result code cannot have multiple interpretations")
    if set(code_groups) - {"positive", "negative", "untested", "indeterminate"}:
        raise ValueError("unsupported result-code category")
    columns: set[str] = set()
    raw_counts: Counter[str] = Counter()
    selected_counts: Counter[str] = Counter()
    identity_counts: Counter[tuple[str, ...]] = Counter()
    missing_identity_rows = 0
    selected_rows = 0
    total_rows = 0
    missing_result_field_rows = 0
    collection_dates: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("record collection must contain objects")
        total_rows += 1
        columns.update(row)
        if fields.get("result"):
            if fields["result"] not in row:
                missing_result_field_rows += 1
            raw_counts[raw_token(row.get(fields["result"]))] += 1
        # With an unreviewed/empty contract, inspect structure only: no cohort claim.
        if not reviewed or not all(key in row and row[key] == value for key, value in filters.items()):
            continue
        selected_rows += 1
        selected_counts[raw_token(row.get(fields["result"]))] += 1
        ids = [row.get(key) for key in identity_columns]
        if any(value is None or value == "" for value in ids):
            missing_identity_rows += 1
        else:
            identity_counts[tuple(raw_token(value) for value in ids)] += 1
        value = row.get(fields["collection_date"])
        if value is not None:
            collection_dates.append(str(value))
    required = set(identity_columns) | set(fields.values()) | set(filters)
    absent = sorted(required - columns)
    if reviewed and absent:
        raise ValueError(f"reviewed source fields absent: {absent}")
    known = {raw_token(code): group for group, values in code_groups.items() for code in values}
    interpreted = {group: 0 for group in ("positive", "negative", "untested", "indeterminate")}
    unmapped = {}
    if reviewed:
        for token, count in selected_counts.items():
            if token in known:
                interpreted[known[token]] += count
            else:
                unmapped[token] = count
    return {
        "source_rows": total_rows, "source_columns": sorted(columns), "source_column_count": len(columns),
        "mapping_reviewed": reviewed, "cohort_filters": filters,
        "selected_rows": selected_rows if reviewed else None,
        "identity_columns": identity_columns, "unique_populated_keys": len(identity_counts) if reviewed else None,
        "duplicate_populated_key_rows": sum(count - 1 for count in identity_counts.values()) if reviewed else None,
        "missing_identity_rows": missing_identity_rows if reviewed else None,
        "result_column": fields.get("result"), "source_raw_result_counts": dict(sorted(raw_counts.items())),
        "source_missing_result_field_rows": missing_result_field_rows if fields.get("result") else None,
        "cohort_raw_result_counts": dict(sorted(selected_counts.items())),
        "cohort_code_interpretation_counts": interpreted if reviewed else None,
        "cohort_unmapped_codes": unmapped if reviewed else None,
        "collection_date_raw_lexical_range": [min(collection_dates), max(collection_dates)] if collection_dates else None,
        "collection_date_note": "Lexical source strings only; no date parsing or chronology claim in M1.",
        "readiness": "cohort_inspected" if reviewed and selected_rows and not unmapped else "review_required",
        "training_eligible": False,
        "warning": "Inspection only. No rows cleaned, labels generated, features built or tables merged.",
    }


def inspect_fsis(path: Path, contract: dict[str, Any]) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, delimiter=contract.get("csv_delimiter", ","))
            names = reader.fieldnames
            if not names or len(names) != len(set(names)):
                raise ValueError("CSV needs a nonempty, unique header")
            def records() -> Iterable[dict[str, Any]]:
                for row in reader:
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError("CSV row width differs from header")
                    yield row
            return {"format": "csv", **profile_rows(records(), contract)}
    if suffix != ".json":
        raise ValueError("FSIS intake accepts JSON or CSV, not an HTML landing page")
    if path.stat().st_size > 128 * 1024 * 1024:
        raise ValueError("JSON inspection capped at 128 MiB; use a single-FY release or add a bounded parser")
    with path.open(encoding="utf-8-sig") as stream:
        payload = json.load(stream)
    if isinstance(payload, dict) and payload.get("@type") == "dcat:Dataset":
        raise ValueError("catalog metadata is not an FSIS sample release; its distribution array is not sample data")
    candidates = record_arrays(payload)
    pointer = contract.get("records_pointer")
    if pointer is None:
        if len(candidates) != 1:
            return {
                "format": "json", "readiness": "records_pointer_required", "candidate_record_pointers": candidates,
                "training_eligible": False,
                "reason": "Provide an explicit records_pointer; do not mistake dictionary arrays for sample records.",
            }
        pointer = candidates[0]
    try:
        records = json_pointer(payload, pointer)
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ValueError(f"records_pointer does not identify a source collection: {pointer}") from error
    if not isinstance(records, list):
        raise ValueError("records_pointer must select an array")
    return {
        "format": "json", "records_pointer": pointer, "candidate_record_pointers": candidates,
        "top_level_keys": sorted(payload) if isinstance(payload, dict) else [],
        **profile_rows(records, contract),
    }
