"""Validate and document M4 source contracts without materializing mapped data.

Run: PYTHONPATH=src python -m tracefront_data.contracts
Runtime: Python 3.11+ standard library only. No dataframe or schema framework.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import io
import json
from pathlib import Path
import re

from tracefront_data.audit import sha256_file
from tracefront_data.clean import output_hashes, verify_baseline
from tracefront_data.provenance import inside_root

ROLES = {"LINEAGE", "IDENTIFIER", "CONTEXT", "REFERENCE_TIME", "MEASUREMENT",
         "OUTCOME_EVIDENCE", "RETROSPECTIVE_CONTEXT", "QUALITY_METADATA"}
LEAKAGE = {"SAFE", "QUESTIONABLE", "LEAKAGE", "LABEL"}
TYPES = {"string", "integer", "decimal", "date", "json"}


def validate_contract(contract: dict, schemas: dict, profiles: dict) -> dict:
    """Structural and semantic guards for all fields; never rename table values."""
    if contract.get("status") != "SOURCE_SPECIFIC_DESIGN_ONLY" or contract.get("data_status") != "NOT MODEL-READY":
        raise ValueError("M4 contracts must remain design-only and NOT MODEL-READY")
    policy = contract["policy"]
    if policy["predictor_allowlist"] or any(policy[k] is not False for k in (
        "mapping_execution_enabled", "label_materialization_enabled", "cross_source_joins_enabled"
    )):
        raise ValueError("Predictors, execution, labels and joins must remain disabled")
    if set(contract["tables"]) != set(schemas) or set(schemas) != set(profiles):
        raise ValueError("Source tables differ from the eligible M2/M3 cohort")
    leakage, pending_units = Counter(), []
    table_names = set()
    field_count = 0
    for key, table in contract["tables"].items():
        schema, profile = schemas[key], profiles[key]
        if table["source_entry"] != schema["source"]["source_entry"]:
            raise ValueError("Source namespace differs from M2")
        if table["data_path"] != profile["input_path"] or table["schema_path"] != str(Path(profile["input_path"]).with_suffix(".schema.json")):
            raise ValueError("Source table/schema paths differ from M3 lineage")
        if set(table["fields"]) != set(schema["columns"]):
            raise ValueError(f"Incomplete or invented field mapping: {key}")
        if table["canonical_table"] in table_names:
            raise ValueError("Canonical source table names must be unique")
        table_names.add(table["canonical_table"])
        if table["row_granularity"] != schema["row_granularity"] or table["null_encoding"] != schema["null_encoding"]:
            raise ValueError("Source grain/null encoding cannot change in M4")
        if table["source"] != schema["source"]:
            raise ValueError("Publisher/source provenance differs from M2")
        if table["predictor_allowlist"] or table["cross_source_join_approved"] is not False:
            raise ValueError("No source predictors or joins are approved in M4")
        availability = table["history_availability"]
        if availability["status"] != "PENDING" or availability["available_at"] is not None:
            raise ValueError("Historical availability cannot be inferred from reference/event dates")
        names = []
        for source_column, field in table["fields"].items():
            field_count += 1
            spec = schema["columns"][source_column]
            canonical = field["canonical_name"]
            if not re.fullmatch(r"[a-z][a-z0-9_]*", canonical):
                raise ValueError("Canonical names must be explicit snake_case")
            names.append(canonical)
            if field["datatype"] not in TYPES or field["datatype"] != spec["datatype"]:
                raise ValueError("M4 cannot narrow/coerce M2 datatypes")
            if field["nullable"] is not spec.get("nullable", False):
                raise ValueError("Source nullability differs from M2 schema")
            if field["observed_null_count"] != profile["null_counts"][source_column]:
                raise ValueError("Observed null counts differ from M3")
            for required in ("description", "missingness", "m2_transformations", "original_location", "leakage_note"):
                if not isinstance(field.get(required), str) or not field[required].strip():
                    raise ValueError("Dictionary descriptions must be explicit: " + required)
            if not isinstance(field["original_columns"], list):
                raise ValueError("Publisher field lineage must be explicit")
            if field["m4_operation"] != "DECLARATION_ONLY_RENAME" or field["predictor_approved"] is not False:
                raise ValueError("Mapped values/predictors cannot be emitted or approved in M4")
            role, classification = field["role"], field["leakage_class"]
            if role not in ROLES or classification not in LEAKAGE:
                raise ValueError("Unknown role or leakage class")
            if role == "OUTCOME_EVIDENCE" and classification != "LABEL":
                raise ValueError("Analytical outcomes must stay label evidence, not predictors")
            if role == "RETROSPECTIVE_CONTEXT" and classification != "LEAKAGE":
                raise ValueError("Retrospective fields must retain focal leakage classification")
            if classification == "SAFE" and role not in {"LINEAGE", "IDENTIFIER"}:
                raise ValueError("SAFE is metadata-only in the current contract")
            expected_status = "NOT_A_PREDICTOR" if role in {"LINEAGE", "IDENTIFIER", "OUTCOME_EVIDENCE", "RETROSPECTIVE_CONTEXT"} else "PENDING"
            if field["prediction_time_availability"]["status"] != expected_status:
                raise ValueError("Prediction availability has not been demonstrated")
            if field["allowed_values"]["observed_values_are_exhaustive_for_future_releases"] is not False:
                raise ValueError("Snapshot vocabulary is not a future-release taxonomy")
            unit = field["unit"]
            if unit["status"] == "PENDING":
                if unit["canonical"] is not None or field["semantic_status"] != "PENDING_UNIT_VERIFICATION":
                    raise ValueError("Pending physical units must remain unresolved")
                pending_units.append(key + "." + source_column)
            if unit.get("unit_column") and unit["unit_column"] not in {f["canonical_name"] for f in table["fields"].values()}:
                raise ValueError("Unit-column reference is absent")
            leakage[classification] += 1
        if len(names) != len(set(names)):
            raise ValueError("Two source columns map to the same canonical column")
        if not table["primary_key"] or set(table["primary_key"]) - set(names):
            raise ValueError("Primary key must reference mapped source fields")
        for group in table["grouping_keys"]:
            if not group or set(group) - set(names):
                raise ValueError("Grouping key must reference mapped source fields")
        fields = table["fields"]
        source = table["source_entry"]
        if source == "usda_pdp":
            if "source_id" in fields and fields["source_id"]["canonical_name"] != "pdp_sample_id_suffix_code":
                raise ValueError("PDP SOURCE_ID is not supplier identity")
            if "lab" in fields and fields["lab"]["canonical_name"] != "pdp_laboratory_code":
                raise ValueError("PDP LAB is not a factory")
            if "mean" in fields and set(fields["mean"]["allowed_values"]["documented_code_meanings"]) != {"ND", "NP", "O", "R"}:
                raise ValueError("PDP result-code distinctions must survive")
        if source.startswith("opendosm_") and "production" in fields:
            production = fields["production"]
            if production["unit"]["status"] != "PENDING" or production["canonical_name"] != "dosm_production_value":
                raise ValueError("OpenDOSM production units remain pending")
        if source == "noaa_ghcn_daily":
            if fields["value"]["canonical_name"] != "ghcn_measurement_value":
                raise ValueError("Station weather is not a batch temperature feature")
            for flag in ("measurement_flag", "quality_flag", "source_flag"):
                if fields[flag]["datatype"] != "string":
                    raise ValueError("NOAA flags must retain literal source characters")
    if set(contract["pending_sources"]) != {"fsis_raw_poultry", "fda_inspections"}:
        raise ValueError("Pending sources must stay separate")
    if any(s["mappings"] for s in contract["pending_sources"].values()):
        raise ValueError("Pending source schemas cannot be fabricated")
    return {"source_tables": len(schemas), "mapped_fields": field_count,
            "leakage_class_counts": dict(sorted(leakage.items())), "pending_unit_fields": sorted(pending_units),
            "approved_predictors": 0, "data_tables_written": 0, "labels_created": 0}


def load_verified_inputs(root: Path) -> tuple[dict, dict, dict, dict]:
    """Reuse M3 typed-census evidence only when all pinned upstream bytes match."""
    m3_validation = json.loads((root / "reports/m3_validation.json").read_text())
    if m3_validation["status"] != "COMPLETE":
        raise ValueError("M3 is not complete")
    evidence = {}
    for relative, metadata in m3_validation["report_artifacts"].items():
        path = inside_root(root, relative)
        if sha256_file(path) != metadata["sha256"] or path.stat().st_size != metadata["size_bytes"]:
            raise ValueError("M3 report changed: " + relative)
        evidence[relative] = metadata["sha256"]
    for relative, digest in m3_validation["code_sha256"].items():
        if sha256_file(inside_root(root, relative)) != digest:
            raise ValueError("M3 producer/test code changed")
    m3 = json.loads((root / "reports/m3_eda_summary.json").read_text())
    for relative, digest in m3["inputs"].items():
        if sha256_file(inside_root(root, relative)) != digest:
            raise ValueError("M3 input fingerprint changed")
        evidence[relative] = digest
    m2 = json.loads((root / "reports/m2_cleaning_summary.json").read_text())
    if sha256_file(inside_root(root, m2["source_manifest"])) != m2["source_manifest_sha256"]:
        raise ValueError("Frozen M1 source manifest changed")
    for relative, digest in m2["cleaning_code_sha256"].items():
        if sha256_file(Path(__file__).parent / relative) != digest:
            raise ValueError("M2 producer code changed")
    source_manifest, raw = verify_baseline(root, inside_root(root, m2["source_manifest"]))
    eligible = {k for k,v in source_manifest["datasets"].items() if v.get("m2_eligible") is True}
    if eligible != set(m2["sources"]) or eligible != set(m3["sources"]):
        raise ValueError("Upstream cohort differs from explicit M1 eligibility")
    directory = inside_root(root, m2["output_directory"])
    if output_hashes(directory) != m2["outputs"]:
        raise ValueError("M2 source bytes/schema/ledgers changed")
    schemas, profiles = {}, {}
    for source, info in m2["sources"].items():
        for table in info["tables"]:
            key = source + "." + table
            path = directory / info["output_subdirectory"] / (table + ".schema.json")
            schemas[key] = json.loads(path.read_text())
            profiles[key] = m3["sources"][source]["tables"][table]
            evidence[path.relative_to(root).as_posix()] = sha256_file(path)
    evidence["reports/m3_validation.json"] = sha256_file(root / "reports/m3_validation.json")
    return schemas, profiles, source_manifest, {"input_sha256": evidence, "raw_verification": raw,
        "m2_output_files_checked": len(m2["outputs"]),
        "typed_readback_evidence": "Reused matching M3 full typed census; no new row transformations or full EDA scan"}


def dictionary_rows(contract: dict) -> list[dict]:
    rows = []
    for key, table in sorted(contract["tables"].items()):
        for source_column, field in table["fields"].items():
            rows.append({"source_table": key, "canonical_table": table["canonical_table"],
                "canonical_name": field["canonical_name"], "publisher": table["source"]["publisher"],
                "original_dataset": table["source_entry"], "original_location": field["original_location"],
                "original_columns": ", ".join(field["original_columns"]) or "positional/M2 lineage; no publisher column",
                "original_position_semantics": field.get("original_position_semantics", ""),
                "m2_column": source_column, "datatype": field["datatype"], "unit": json.dumps(field["unit"], sort_keys=True),
                "description": field["description"], "nullable": field["nullable"], "observed_null_count": field["observed_null_count"],
                "allowed_values": json.dumps(field["allowed_values"], sort_keys=True), "missingness": field["missingness"],
                "transformations_applied": field["m2_transformations"], "m4_operation": field["m4_operation"],
                "prediction_time_availability": field["prediction_time_availability"]["status"],
                "availability_reason": field["prediction_time_availability"]["reason"],
                "role": field["role"], "leakage_class": field["leakage_class"], "leakage_note": field["leakage_note"],
                "predictor_approved": field["predictor_approved"], "semantic_status": field["semantic_status"]})
    return rows


def markdown(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_dictionary(contract: dict) -> tuple[str, str]:
    rows = dictionary_rows(contract)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    lines = ["# M4 — Source-specific data dictionary", "", "**Design only. NOT MODEL-READY. No mapped data tables or final labels were created.**", "",
             "Authoritative machine-readable metadata: `configs/source_contracts.json`. Filterable full dictionary: `reports/m4_data_dictionary.csv`.", "",
             "Names are scoped by canonical source table. Every M2 column is covered. Original field names, types, units, allowed/source-observed values, transformations, missingness, availability and leakage are retained in the JSON/CSV. Observed vocabularies are not future-release whitelists.", "",
             "All predictor allowlists are empty. SAFE identifies lineage/grouping metadata only. LABEL identifies existing analytical evidence, not a newly defined target. LEAKAGE is relative to a focal decision before retrospective fields became available; historic use still requires version/availability proof.", "",
             "Date-only records stay dates. Historical availability is PENDING for every table; no available_at or prediction_time is fabricated. M2 nullability is preserved, even where accepted identity keys happen to be nonnull; keys are required separately within their snapshot namespace.", "",
             "PDP sample/result tables, recall records, daily weather elements and the three agricultural aggregates remain independent. The M0 batch-level draft is a separate future design, not a schema these records must fill."]
    for key, table in sorted(contract["tables"].items()):
        lines += ["", "## " + key + " → " + table["canonical_table"], "",
                  "Grain: " + table["row_granularity"], "",
                  "Identity: `" + ", ".join(table["primary_key"]) + "`. Scope: " + table["key_scope"], "",
                  "| Canonical name | Publisher → M2 column | Type / unit | Meaning; null/allowed semantics; M2 transformation | Availability / leakage |",
                  "| --- | --- | --- | --- | --- |"]
        for row in (r for r in rows if r["source_table"] == key):
            field = table["fields"][row["m2_column"]]
            unit = field["unit"]
            unit_text = ("via " + unit["unit_column"] if unit.get("unit_column") else str(unit["canonical"] or unit["source_declared"] or "n/a")) + " (" + unit["status"] + ")"
            allowed = field["allowed_values"]
            codes = allowed.get("documented_code_meanings") or allowed.get("observed_values")
            values = (" Codes/observed snapshot values: " + json.dumps(codes, ensure_ascii=False)) if codes is not None and len(codes) <= 12 else " Larger/open vocabulary: see JSON/CSV."
            explanation = row["description"] + " Null allowed: " + str(row["nullable"]) + "; observed nulls: " + str(row["observed_null_count"]) + ". " + row["missingness"] + " " + allowed["constraints"] + values + " " + row["transformations_applied"]
            lines.append("| " + " | ".join(markdown(v) for v in (
                row["canonical_name"], row["original_columns"] + " → " + row["m2_column"],
                row["datatype"] + " / " + unit_text, explanation,
                row["prediction_time_availability"] + " / " + row["leakage_class"] + ": " + row["leakage_note"])) + " |")
    lines += ["", "## Explicit holds and unsupported fields", "",
              "- OpenDOSM production units remain PENDING; dosm_production_value has no approved canonical physical unit. Publisher metric-tonne claims are retained as evidence, not used to resolve the flower-unit question.",
              "- SOURCE_ID is a PDP sample-ID suffix; LAB is an analytical lab. Neither is a supplier/factory join key. QUANTITY counts selected sample units, not batch size.",
              "- PDP CONCEN/LOD/MEAN/ANNOTATE/methods are analytical evidence and cannot enter the same-endpoint predictor list. ND/NP are distinct nondetect qualities. No tolerance comparison or final chemical label was created.",
              "- NOAA preserves separate elements, units, MFLAG/QFLAG/SFLAG and observation status. A daily station value is not a supply-chain sensor or product-core reading.",
              "- Recall snapshot fields are not as-of records. Firm addresses are not food origins; event_id is grouping, not a unique product record ID.",
              "- OpenDOSM annual reference years are not publication timestamps. District tables cover 2017; state totals overlap national totals. No table is joined or summed here.",
              "- FSIS: official source confirmed, raw file not yet acquired. FDA inspections pending. Both have empty mappings.", ""]
    lines += ["- `" + name + "`: " + reason for name, reason in contract["unsupported_batch_fields"].items()]
    return "\n".join(lines) + "\n", stream.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Validate metadata and upstream bytes without writing reports")
    args = parser.parse_args()
    root = Path.cwd()
    contract_path = root / "configs/source_contracts.json"
    contract = json.loads(contract_path.read_text())
    schemas, profiles, _, evidence = load_verified_inputs(root)
    checks = validate_contract(contract, schemas, profiles)
    if args.check_only:
        print(json.dumps({"integrity_ok": True, **checks}, indent=2))
        return
    md, csv_text = render_dictionary(contract)
    reports = root / "reports"
    (reports / "m4_data_dictionary.md").write_text(md, encoding="utf-8")
    (reports / "m4_data_dictionary.csv").write_text(csv_text, encoding="utf-8", newline="")
    evidence.update(milestone="M4", status="COMPLETE", scope="Source-specific contract design and metadata validation only",
                    data_status="NOT MODEL-READY", contract_sha256=sha256_file(contract_path),
                    validator_sha256=sha256_file(Path(__file__)), checks=checks,
                    outputs={p:sha256_file(reports / p) for p in ("m4_data_dictionary.md", "m4_data_dictionary.csv")},
                    runtime_dependencies_added=[], s390x_executed=False)
    (reports / "m4_schema_summary.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "COMPLETE", **checks}, indent=2))


if __name__ == "__main__":
    main()
