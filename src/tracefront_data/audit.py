"""Read-only audit of a local openFDA enforcement snapshot; no network access.

Run from the repository root:
    PYTHONPATH=src python -m tracefront_data.audit --input PATH --output PATH
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
import logging
from pathlib import Path
from typing import Any
import zipfile

LOGGER = logging.getLogger(__name__)
DATE_FIELDS = (
    "report_date", "recall_initiation_date", "center_classification_date",
    "termination_date",
)


def is_missing(value: Any) -> bool:
    """Treat absent/null, empty strings/containers, and whitespace as missing.

    Zero and False are observed values. No values are imputed or modified.
    """
    return value is None or (isinstance(value, str) and not value.strip()) or (
        isinstance(value, (list, dict)) and not value
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure fields, missingness, duplicate identity, and date anomalies.

    Date plausibility is an audit flag (pre-2000), not a correction rule.
    Records remain at source granularity. Nested values are not flattened.
    """
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError("results must be a list of JSON objects")
    columns = sorted({key for row in records for key in row})
    identifiers: dict[str, Any] = {}
    for key in ("recall_number", "event_id"):
        counts = Counter(str(row[key]) for row in records if not is_missing(row.get(key)))
        identifiers[key] = {
            "missing": sum(is_missing(row.get(key)) for row in records),
            "unique_nonmissing": len(counts),
            "duplicate_nonmissing_rows": sum(count - 1 for count in counts.values()),
        }
    dates: dict[str, Any] = {}
    for key in DATE_FIELDS:
        parsed: list[date] = []
        invalid: list[dict[str, Any]] = []
        suspicious: list[dict[str, Any]] = []
        for index, row in enumerate(records):
            value = row.get(key)
            if is_missing(value):
                continue
            record = {"row_index": index, "value": value, "recall_number": row.get("recall_number")}
            try:
                if not isinstance(value, str) or len(value) != 8 or not value.isascii() or not value.isdigit():
                    raise ValueError("expected YYYYMMDD")
                parsed_date = date(int(value[:4]), int(value[4:6]), int(value[6:]))
            except ValueError:
                invalid.append(record)
                continue
            parsed.append(parsed_date)
            if parsed_date.year < 2000:
                suspicious.append(record)
        dates[key] = {
            "parsed_min": min(parsed).isoformat() if parsed else None,
            "parsed_max": max(parsed).isoformat() if parsed else None,
            "invalid_count": len(invalid),
            "invalid_examples": invalid[:20],
            "pre_2000_count": len(suspicious),
            "pre_2000_examples": suspicious[:20],
        }
    return {
        "rows": len(records),
        "column_count": len(columns),
        "columns": columns,
        "missingness_definition": "absent, null, whitespace/empty string, empty list or object",
        "missing_counts": {key: sum(is_missing(row.get(key)) for row in records) for key in columns},
        "exact_duplicate_rows": len(records) - len({json.dumps(row, sort_keys=True) for row in records}),
        "identifiers": identifiers,
        "dates": dates,
        "category_counts": {
            key: dict(sorted(Counter(str(row[key]) for row in records if not is_missing(row.get(key))).items()))
            for key in ("classification", "status", "product_type", "country")
        },
        "rows_removed": 0,
        "rows_changed": 0,
        "training_eligible": False,
        "training_ineligibility_reason": "Recall records are not a tested-positive/negative sample cohort.",
    }


def audit_snapshot(path: Path, archive_path: Path | None = None) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict) or "results" not in payload:
        raise ValueError("expected an openFDA JSON object with results")
    result = {
        "audit_version": 1,
        "input_path": path.as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "source_metadata_unverified": payload.get("meta", {}),
        **audit_records(payload["results"]),
    }
    if archive_path is not None:
        with zipfile.ZipFile(archive_path) as archive:
            bad_member = archive.testzip()
            member_hash = hashlib.sha256()
            with archive.open(path.name) as member:
                for chunk in iter(lambda: member.read(1024 * 1024), b""):
                    member_hash.update(chunk)
            result["archive"] = {
                "input_path": archive_path.as_posix(),
                "size_bytes": archive_path.stat().st_size,
                "sha256": sha256_file(archive_path),
                "members": archive.namelist(),
                "crc_error_member": bad_member,
                "member_matches_input": member_hash.hexdigest() == result["sha256"],
            }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    output = args.output.resolve()
    if output in {p.resolve() for p in (args.input, args.archive) if p is not None}:
        parser.error("output must not overwrite a source file")
    report = audit_snapshot(args.input, args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LOGGER.info("Audited %s rows and %s fields; source unchanged; report: %s",
                report["rows"], report["column_count"], args.output)


if __name__ == "__main__":
    main()
