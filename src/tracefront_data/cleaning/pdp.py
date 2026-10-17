"""Clean the reviewed PDP annual sample and analytical tables separately."""

from __future__ import annotations

import csv
from collections import Counter
from datetime import date
from decimal import Decimal
import io
from pathlib import Path
import zipfile

from tracefront_data.audit import sha256_file
from tracefront_data.cleaning.common import Duplicates, Table, conflicts, identifier, number, string_columns, text


def clean_pdp(archive_path: Path, directory: Path, schema: dict, cutoff: date, source: dict,
              scratch: Path) -> dict:
    if sha256_file(archive_path) != schema["reviewed_archive_sha256"]:
        raise ValueError("PDP archive differs from reviewed dictionary mapping")
    sample_names = schema["sample_columns"]
    result_names = schema["result_columns"]
    sample_columns = string_columns([n.lower() for n in sample_names])
    sample_columns.update(year={"datatype": "integer", "unit": "calendar year"},
                          month={"datatype": "integer"}, day={"datatype": "integer"},
                          quantity={"datatype": "integer", "nullable": True},
                          country_missing_reason={"datatype": "string", "nullable": True},
                          collection_date={"datatype": "date", "temporal_semantics": "collection date; not result availability"})
    samples = Table(directory, "samples", sample_columns, grain="PDP 2024 sample identity record",
                    source=source | {"archive_member": schema["sample_member"]},
                    transformations=["Trim surrounding whitespace; preserve opaque string IDs and codes",
                                     "Interpret YEAR=24 only within this explicitly reviewed 2024 release; validate calendar date",
                                     "Parse optional QUANTITY as nonnegative integer; no imputation",
                                     "Remove exact repeated sample PK rows; quarantine all conflicting PK versions"],
                    missing_semantics=["Empty/whitespace becomes null, except documented SOURCE_ID blank default",
                                       "SOURCE_ID blank is the documented default, not unknown",
                                       "COUNTRY absent for domestic/unknown origin is retained null, not inferred",
                                       "VARIETY literal N/A/Na tokens are retained because free-text meaning is ambiguous"])
    valid_ids = set()
    with zipfile.ZipFile(archive_path) as archive:
        with io.TextIOWrapper(archive.open(schema["sample_member"]), encoding="utf-8", newline="") as stream:
            rows = list(csv.reader(stream, delimiter="|", strict=True))
        mapped = [dict(zip(sample_names, row)) for row in rows if len(row) == len(sample_names)]
        conflicting = conflicts(mapped, ["SAMPLE_PK"])
        seen = {}
        for row_number, row in enumerate(rows, 1):
            raw = dict(zip(sample_names, row))
            samples.observe(raw)
            if len(row) != len(sample_names):
                samples.stats["malformed_rows"] += 1
                samples.reject(row_number, row, ["malformed_field_count"])
                continue
            values = {n.lower(): text(raw[n]) for n in sample_names}
            values["source_id"] = raw["SOURCE_ID"].strip()
            values["country_missing_reason"] = (None if values["country"] is not None else
                "not_applicable_domestic" if values["origin"] == "1" else
                "origin_unknown" if values["origin"] == "3" else "unprovided_import_country")
            pk = values["sample_pk"]
            errors = []
            if not pk:
                samples.stats["missing_critical_identifiers"] += 1
            try:
                identifier(pk)
            except ValueError:
                errors.append("missing_or_invalid_sample_pk")
            if pk in seen:
                samples.stats["duplicate_rows"] += 1
                if (pk,) not in conflicting:
                    errors.append("duplicate_sample_pk_exact")
            seen.setdefault(pk, row_number)
            if (pk,) in conflicting:
                errors.append("conflicting_sample_pk_all_versions_quarantined")
            try:
                if raw["YEAR"].strip() != "24":
                    raise ValueError("unexpected source year")
                collection = date(2024, int(raw["MONTH"]), int(raw["DAY"]))
                if collection > cutoff:
                    raise ValueError("future sample date")
                values.update(year=2024, month=collection.month, day=collection.day,
                              collection_date=collection.isoformat())
            except (ValueError, TypeError):
                samples.stats["invalid_date_rows"] += 1
                errors.append("invalid_collection_date")
            try:
                values["quantity"] = number(raw["QUANTITY"], integer=True, minimum="0")
            except ValueError:
                samples.stats["invalid_numeric_rows"] += 1
                errors.append("invalid_quantity")
            if errors:
                samples.reject(row_number, raw, errors, pk)
            else:
                valid_ids.add(pk)
                samples.accept(row_number, values)
        sample_stats = samples.close()

        result_columns = string_columns([n.lower() for n in result_names])
        for name in ("concen", "lod"):
            result_columns[name] = {"datatype": "decimal", "unit_column": "conunit", "nullable": True,
                                    "role": "analytical outcome" if name == "concen" else "assay metadata"}
        result_columns.update(concen_raw={"datatype": "string", "role": "unaltered concentration token"},
                              concen_missing_reason={"datatype": "string", "nullable": True, "role": "measurement missingness"},
                              duplicate_of_source_row={"datatype": "integer", "nullable": True, "role": "lineage"})
        results = Table(directory, "results", result_columns, grain="PDP analytical result; multiple analytes/extractions per sample",
                        source=source | {"archive_member": schema["result_member"]},
                        transformations=["Trim code boundaries; parse finite nonnegative decimals, retaining native CONUNIT",
                                         "Preserve MEAN ND/NP/O/R and ANNOTATE verbatim after boundary trimming",
                                         "Validate reference to accepted release-local sample IDs without joining tables",
                                         "Flag and retain exact analytical duplicates; sample/analyte is not assumed unique"],
                        missing_semantics=["Blank CONCEN stays null; original token retained in concen_raw",
                                           "ND and NP censoring remain distinct; no zero imputation",
                                           "Blank ANNOTATE means no annotation, retained as non-null empty string",
                                           "Missing CONCEN/LOD in detection rows is flagged, not assigned an outcome",
                                           "Untested analytes remain absent; no synthetic negatives created"])
        duplicate_store = Duplicates(scratch / "pdp_result_duplicates.sqlite")
        preserved_codes: Counter[str] = Counter()
        try:
            with io.TextIOWrapper(archive.open(schema["result_member"]), encoding="utf-8", newline="") as stream:
                for row_number, row in enumerate(csv.reader(stream, delimiter="|", strict=True), 1):
                    raw = dict(zip(result_names, row))
                    results.observe(raw)
                    if len(row) != len(result_names):
                        results.stats["malformed_rows"] += 1
                        results.reject(row_number, row, ["malformed_field_count"])
                        continue
                    values = {n.lower(): text(raw[n]) for n in result_names}
                    values["annotate"] = raw["ANNOTATE"].strip()
                    values["concen_raw"] = raw["CONCEN"]
                    values["concen_missing_reason"] = None
                    previous = duplicate_store.previous(row, row_number)
                    values["duplicate_of_source_row"] = previous
                    if previous is not None:
                        results.stats["duplicate_rows"] += 1
                        results.issue(row_number, "exact_analytical_duplicate_retained", raw_value=previous)
                    errors = []
                    pk = values["sample_pk"]
                    if not pk:
                        results.stats["missing_critical_identifiers"] += 1
                    if pk not in valid_ids:
                        errors.append("sample_pk_not_in_accepted_sample_table")
                    if values["mean"] not in schema["mean_code_meanings"]:
                        errors.append("unknown_or_missing_mean_code")
                    numeric_bad = False
                    for column in ("CONCEN", "LOD"):
                        try:
                            values[column.lower()] = number(raw[column], minimum="0")
                            if column == "LOD" and values["lod"] is not None and Decimal(values["lod"]) == 0:
                                raise ValueError("zero detection limit")
                        except ValueError:
                            numeric_bad = True
                            errors.append("invalid_" + column.lower())
                    results.stats["invalid_numeric_rows"] += numeric_bad
                    if errors:
                        results.reject(row_number, raw, errors, pk)
                        continue
                    if values["concen"] is None:
                        values["concen_missing_reason"] = ("censored_" + values["mean"]
                            if values["mean"] in {"ND", "NP"} else "unknown_despite_detection_code")
                        if values["mean"] in {"O", "R"}:
                            results.issue(row_number, "missing_concentration_for_detection", "CONCEN", raw["CONCEN"])
                    elif values["mean"] in {"ND", "NP"}:
                        results.issue(row_number, "numeric_concentration_with_nondetect_code", "CONCEN", raw["CONCEN"])
                    if values["lod"] is None:
                        results.issue(row_number, "missing_detection_limit", "LOD", raw["LOD"])
                    if values["conunit"] not in {"M", "B", "T"}:
                        results.issue(row_number, "unknown_concentration_unit_retained", "CONUNIT", raw["CONUNIT"])
                    results.accept(row_number, values)
                    preserved_codes[values["mean"]] += 1
                    if row_number % 500_000 == 0:
                        print(f"PDP analytical records inspected: {row_number:,}", flush=True)
        finally:
            duplicate_store.close()
        result_stats = results.close()
        result_stats["preserved_mean_code_counts"] = dict(sorted(preserved_codes.items()))
    return {"tables": {"samples": sample_stats, "results": result_stats},
            "accepted_sample_ids": len(valid_ids), "analytical_foreign_key_policy": "Only accepted same-release sample IDs; no table join",
            "duplicate_definition": "Samples: extra PK occurrences; results: exact raw analytical-row repeats retained and linked",
            "known_ambiguities": ["Original and re-extraction rows are not automatically one independent sample/analyte observation",
                                  "VARIETY N/A/Na tokens can mean unknown or not applicable and are retained literally",
                                  "No effective-date regulatory tolerance/residue-definition comparison performed"]}
