"""Independent recall and annual agriculture cleaners; no enrichment joins."""

from __future__ import annotations

import csv
from datetime import date
import json
from pathlib import Path

from tracefront_data.cleaning.common import Table, conflicts, number, parse_date, string_columns, text


def clean_openfda(path: Path, directory: Path, columns: list[str], cutoff: date, source: dict) -> dict:
    records = json.loads(path.read_text())["results"]
    dates = ["recall_initiation_date", "termination_date", "report_date", "center_classification_date"]
    output_columns = string_columns(columns)
    output_columns["openfda"] = {"datatype": "json", "nullable": True}
    for column in dates:
        output_columns[column] = {"datatype": "date", "nullable": True, "availability_warning": "Not an as-of field version"}
        output_columns[column + "_raw"] = {"datatype": "string", "nullable": True, "role": "unaltered source date token"}
    table = Table(directory, "recalls", output_columns, grain="Product-specific food recall enforcement record; event_id can repeat",
                  source=source,
                  transformations=["Trim text boundaries; blank/null to explicit CSV null",
                                   "Parse strict YYYYMMDD to ISO dates in 1900..frozen retrieval-date window",
                                   "Invalid optional dates become null with original token and issue evidence",
                                   "Reject missing recall_number or missing/invalid report_date; quarantine conflicting recall numbers",
                                   "Remove exact repeated recall records, never deduplicate by event_id",
                                   "Normalize only documented classification/status casing; retain other categories"],
                  missing_semantics=["Null is unknown/unprovided, not no recall or tested negative",
                                     "An empty openfda object is retained as {}, not made a missing scalar",
                                     "Free text such as N/A is not blindly converted to null",
                                     "Invalid optional dates are distinguishable from absent dates via raw tokens/issues"])
    bad = conflicts(records, ["recall_number"])
    seen = set()
    allowed = {"classification": {v.lower(): v for v in ["Class I", "Class II", "Class III", "Not Yet Classified"]},
               "status": {v.lower(): v for v in ["Ongoing", "Completed", "Terminated"]}}
    for row_number, raw in enumerate(records, 1):
        table.observe(raw)
        errors = []
        if set(raw) - set(columns) or any(not isinstance(v, str) and v is not None for k, v in raw.items() if k != "openfda"):
            table.stats["malformed_rows"] += 1
            table.reject(row_number, raw, ["unexpected_record_fields_or_types"])
            continue
        values = {k: text(raw.get(k)) for k in columns if k != "openfda"}
        if not isinstance(raw.get("openfda"), (dict, type(None))):
            table.stats["malformed_rows"] += 1
            table.reject(row_number, raw, ["unexpected_openfda_object_type"])
            continue
        values["openfda"] = json.dumps(raw["openfda"], sort_keys=True, ensure_ascii=False) if raw.get("openfda") is not None else None
        key = values["recall_number"]
        if not key:
            table.stats["missing_critical_identifiers"] += 1
            errors.append("missing_recall_number")
        if key in seen:
            table.stats["duplicate_rows"] += 1
            if (key,) not in bad:
                errors.append("exact_duplicate_recall_record")
        seen.add(key)
        if (key,) in bad:
            errors.append("conflicting_recall_number_all_versions_quarantined")
        invalid_date = False
        for column in dates:
            values[column + "_raw"] = raw.get(column)
            try:
                values[column] = parse_date(raw.get(column), "%Y%m%d", cutoff)
                if column == "report_date" and values[column] is None:
                    raise ValueError("missing report date")
            except ValueError:
                invalid_date = True
                values[column] = None
                table.issue(row_number, "invalid_" + column, column, raw.get(column))
                if column == "report_date":
                    errors.append("missing_or_invalid_report_date")
        table.stats["invalid_date_rows"] += invalid_date
        for column, mapping in allowed.items():
            value = values[column]
            if value:
                values[column] = mapping.get(value.lower(), value)
                if value.lower() not in mapping:
                    table.issue(row_number, "unexpected_" + column + "_retained", column, raw.get(column))
        if errors:
            table.reject(row_number, raw, errors, key)
        else:
            table.accept(row_number, values)
    return {"tables": {"recalls": table.close()}, "intended_role": "HISTORICAL_RISK_SOURCE",
            "duplicate_definition": "Extra occurrences of a recall number; exact repeats removed, all conflicting versions quarantined",
            "known_ambiguities": ["Initiation/event dates do not establish historical public availability of each field",
                                  "Retrospective status, classification and termination fields are not approved predictors"],
            "contamination_label_created": False}


def clean_opendosm(path: Path, directory: Path, name: str, columns: list[str], cutoff: date, source: dict) -> dict:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != columns:
            raise ValueError("OpenDOSM header differs from frozen inspected schema")
        rows = list(reader)
    geography = ["state"] + (["district"] if "district" in columns else [])
    keys = ["date", *geography, "crop_type"] + (["crop_species"] if "crop_species" in columns else [])
    metrics = [n for n in ("production", "planted_area") if n in columns]
    output_columns = string_columns([n if n != "date" else "reference_date" for n in columns])
    output_columns["reference_date"] = {"datatype": "date", "temporal_semantics": "Annual reference marker; not observation/publication time"}
    output_columns["reference_year"] = {"datatype": "integer", "unit": "calendar year"}
    for metric in metrics:
        output_columns[metric] = {"datatype": "decimal", "nullable": True,
                                  "unit": "metric tonnes" if metric == "production" else "hectares"}
    table = Table(directory, name, output_columns, grain=("Annual state/country x crop type" if "district" not in columns
                  else "Annual state x district x crop type x species"), source=source,
                  transformations=["Trim categorical/name boundaries without fuzzy spelling or geography matching",
                                   "Validate annual YYYY-01-01 reference marker; emit reference_date/reference_year",
                                   "Parse finite nonnegative production/area; preserve null and zero distinction",
                                   "Remove exact repeated aggregate keys; quarantine all conflicting key versions"],
                  missing_semantics=["Empty/whitespace means unknown/unprovided, never implicitly zero",
                                     "Absent district/crop rows are not synthesized",
                                     "Reference year/date is not an event timestamp or public-availability time",
                                     "National/state totals and separate district tables remain independent"])
    valid_shape = [r for r in rows if None not in r and all(v is not None for v in r.values())]
    bad = conflicts(valid_shape, keys)
    seen = set()
    for row_number, raw in enumerate(rows, 1):
        table.observe(raw)
        if None in raw or any(v is None for v in raw.values()):
            table.stats["malformed_rows"] += 1
            table.reject(row_number, raw, ["malformed_field_count"])
            continue
        values = {n: text(raw[n]) for n in columns if n != "date"}
        key = tuple(text(raw.get(k)) for k in keys)
        errors = []
        if any(v is None for v in key):
            table.stats["missing_critical_identifiers"] += 1
            errors.append("missing_aggregate_key")
        if key in seen:
            table.stats["duplicate_rows"] += 1
            if key not in bad:
                errors.append("exact_duplicate_aggregate")
        seen.add(key)
        if key in bad:
            errors.append("conflicting_aggregate_key_all_versions_quarantined")
        try:
            reference = parse_date(raw["date"], "%Y-%m-%d", cutoff)
            if reference is None or not reference.endswith("-01-01"):
                raise ValueError("not an annual reference marker")
            values.update(reference_date=reference, reference_year=int(reference[:4]))
        except ValueError:
            table.stats["invalid_date_rows"] += 1
            errors.append("invalid_annual_reference_date")
        numeric_bad = False
        for metric in metrics:
            try:
                values[metric] = number(raw[metric], minimum="0")
            except ValueError:
                numeric_bad = True
                errors.append("invalid_" + metric)
        table.stats["invalid_numeric_rows"] += numeric_bad
        if errors:
            table.reject(row_number, raw, errors, "|".join(v or "" for v in key))
        else:
            table.accept(row_number, values)
    return {"tables": {name: table.close()}, "temporal_semantics": "Annual reference date only; publication/availability unknown",
            "conflicting_key_groups": len(bad),
            "duplicate_definition": "Extra natural-key occurrences, including conflicting versions; not the count of all quarantined rows",
            "known_ambiguities": ["Conflicting aggregate versions may reflect publisher duplication or undocumented strata; no winner/sum inferred",
                                  "State/national totals overlap; absent district/crop rows are not assumed zero"]}
