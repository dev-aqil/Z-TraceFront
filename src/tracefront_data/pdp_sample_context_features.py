"""M5 source-specific feature materialization for cleared PDP sample-context families.

Run: PYTHONPATH=src python -m tracefront_data.pdp_sample_context_features

Scope is restricted to the feature families that pass the pinned M5 readiness
assessment (pdp_product_context and pdp_collection_calendar). The module re-checks
that assessment before reading the single pinned usda_pdp.samples M2 table. It
reads no usda_pdp.results field, performs no cross-source or cross-table join,
creates no label, and trains no model. Output is one un-joined, unlabeled,
source-specific feature table under data/interim/m5_v1/ plus its schema, a
summary and a report under reports/m5_*. Python standard library only.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterator

from tracefront_data.audit import sha256_file
from tracefront_data.cleaning.common import encode, read_table
from tracefront_data.feature_readiness import assess_families, verify_m4, verify_m5_evidence
from tracefront_data.provenance import inside_root

SOURCE_TABLE = "usda_pdp.samples"
M2_OUTPUT_DIRECTORY = "data/interim/m2_v1"
M2_SUMMARY_PATH = "reports/m2_cleaning_summary.json"
DEFAULT_OUTPUT_DIRECTORY = "data/interim/m5_v1"
FEATURE_TABLE = "pdp_sample_context_features"
DEFAULT_SUMMARY_PATH = "reports/m5_pdp_sample_context_features_summary.json"
DEFAULT_REPORT_PATH = "reports/m5_pdp_sample_context_features_report.md"

# Only the assessed INPUT references of the cleared families may be materialized.
# Product-context features pass native source codes/values through verbatim:
# no decoding, no taxonomy mapping, no imputation.
PRODUCT_CONTEXT_COLUMNS: dict[str, dict[str, str]] = {
    "commod": {"feature": "pdp_commodity_code", "datatype": "string",
               "unit": "not_applicable", "derivation": "verbatim native PDP commodity code"},
    "commtype": {"feature": "pdp_commodity_type_code", "datatype": "string",
                 "unit": "not_applicable", "derivation": "verbatim native PDP commodity-form code"},
    "origin": {"feature": "pdp_origin_code", "datatype": "string",
               "unit": "not_applicable", "derivation": "verbatim native PDP origin code"},
    "country": {"feature": "pdp_import_origin_country_code", "datatype": "string",
                "unit": "not_applicable",
                "derivation": "verbatim native PDP import-origin country code; null is not imputed"},
    "variety": {"feature": "pdp_variety_text", "datatype": "string",
                "unit": "not_applicable", "derivation": "verbatim publisher free-text variety description"},
    "claim": {"feature": "pdp_product_claim_code", "datatype": "string",
              "unit": "not_applicable", "derivation": "verbatim native PDP label-claim code"},
    "quantity": {"feature": "pdp_sample_unit_count", "datatype": "integer",
                 "unit": "count_individual_sample_units",
                 "derivation": "verbatim nonnegative integer sample-unit count; null is not zero"},
}
# Deterministic calendar context derived only from the validated collection date.
# The existing M2 year/month/day components are NOT emitted as new features.
COLLECTION_CALENDAR_COLUMNS: tuple[dict[str, str], ...] = (
    {"feature": "pdp_collection_dow_iso", "datatype": "integer",
     "unit": "iso_weekday_1_monday_7_sunday",
     "derivation": "ISO weekday (1=Monday..7=Sunday) of the validated collection date"},
    {"feature": "pdp_collection_doy", "datatype": "integer",
     "unit": "day_of_year_1_366",
     "derivation": "day of year (1..366) of the validated collection date"},
    {"feature": "pdp_collection_isoweek", "datatype": "integer",
     "unit": "iso_week_number_1_53",
     "derivation": "ISO week number (1..53) of the validated collection date"},
)
LINEAGE_COLUMNS = ("pdp_source_row_number", "pdp_sample_id")
# Feature nullability mirrors the pinned M2 missingness exactly; any other null
# observed during materialization or readback is a hard error, never a silent zero.
FEATURE_NULLABLE = {"pdp_import_origin_country_code", "pdp_sample_unit_count"}
# Values/markers that must never appear as a feature name: no analytical outcome,
# retrospective field or model-ready pseudo-label is emitted by this module.
FORBIDDEN_NAME_MARKERS = ("label", "contam", "result_code", "concentration",
                          "recall", "inspection", "risk", "target", "censor")
TARGET_FAMILIES = ("pdp_collection_calendar", "pdp_product_context")


def feature_columns() -> list[dict[str, str]]:
    """Feature metadata in output order; lineage columns are excluded."""
    columns = []
    for source_column, spec in PRODUCT_CONTEXT_COLUMNS.items():
        columns.append({"source_column": source_column, "family": "pdp_product_context", **spec})
    for spec in COLLECTION_CALENDAR_COLUMNS:
        columns.append({"source_column": "collection_date", "family": "pdp_collection_calendar", **spec})
    return columns


def feature_names() -> tuple[str, ...]:
    return tuple(column["feature"] for column in feature_columns())


def load_assessment(root: Path) -> tuple[dict, dict, dict]:
    """Re-verify pinned upstream metadata and require the target families cleared."""
    scope_path = root / "configs/m5_feature_scope.json"
    scope = json.loads(scope_path.read_text())
    if scope["source_contract_sha256"] != sha256_file(root / "configs/source_contracts.json"):
        raise ValueError("M5 feature scope does not cover the pinned M4 contract")
    verify_m5_evidence(root, scope)
    contract, _m4_evidence = verify_m4(root)
    assessment = assess_families(contract, scope)
    families = {family["id"]: family for family in assessment["families"]}
    excluded = {(item["table"], item["column"]) for item in assessment["excluded_direct_focal_inputs"]}
    if ("usda_pdp.results", "concen") not in excluded or ("usda_pdp.results", "mean") not in excluded:
        raise ValueError("M4 outcome exclusions are required guardrails; refusing to materialize")
    for family_id in sorted(TARGET_FAMILIES):
        family = families.get(family_id)
        if family is None:
            raise ValueError("Target feature family missing from assessment: " + family_id)
        if family["status"] != "REQUIRES_IMPLEMENTATION_REVIEW" or family["reason_codes"]:
            raise ValueError("Feature family prerequisites are unresolved; nothing may be materialized: "
                             + family_id + " " + ",".join(family["reason_codes"]))
        assessed = family["field_assessments"]
        if not assessed:
            raise ValueError("Cleared family has no assessed inputs: " + family_id)
        for ref in assessed:
            if ref["table"] != SOURCE_TABLE:
                raise ValueError("Cleared family references an unassessed source table; refusing to join: "
                                 + ref["table"])
            if ref["field_availability"] != "M5_VERIFIED" or ref["historical_availability"] != "M5_VERIFIED":
                raise ValueError("Cleared family input lacks M5-verified availability: " + ref["column"])
            if ref["use"] == "INPUT":
                if not ref["predictor_approved"]:
                    raise ValueError("Cleared family input is not an approved predictor: " + ref["column"])
                if ref["unit_readiness"] == "PENDING":
                    raise ValueError("Cleared family input has a pending unit: " + ref["column"])
    if {ref["column"] for ref in families["pdp_product_context"]["field_assessments"]} != set(PRODUCT_CONTEXT_COLUMNS):
        raise ValueError("Assessed product-context columns differ from the materialization preamble")
    if {ref["column"] for ref in families["pdp_collection_calendar"]["field_assessments"]} != {"collection_date"}:
        raise ValueError("Assessed collection-calendar columns differ from the materialization preamble")
    for name in feature_names():
        lowered = name.lower()
        if any(marker in lowered for marker in FORBIDDEN_NAME_MARKERS):
            raise ValueError("Forbidden feature name marker: " + name)
    return contract, scope, assessment


def verify_m2_samples(root: Path) -> tuple[Path, dict]:
    """Pin the exact samples table bytes against the frozen M2 summary before reading."""
    m2 = json.loads((root / M2_SUMMARY_PATH).read_text())
    samples = m2["sources"]["usda_pdp"]["tables"]["samples"]
    directory = root / M2_OUTPUT_DIRECTORY / "usda_pdp"
    for name in ("samples.csv", "samples.schema.json"):
        pinned = m2["outputs"]["usda_pdp/" + name]
        path = directory / name
        if path.stat().st_size != pinned["size_bytes"] or sha256_file(path) != pinned["sha256"]:
            raise ValueError("M2 samples artifact changed: " + name)
    return directory / "samples.csv", samples


def compute_calendar(collection: date) -> dict[str, int]:
    """Deterministic calendar context; never an assay-timing or availability claim."""
    return {"pdp_collection_dow_iso": collection.isoweekday(),
            "pdp_collection_doy": collection.timetuple().tm_yday,
            "pdp_collection_isoweek": collection.isocalendar()[1]}


def assemble_row(sample: dict[str, Any]) -> dict[str, Any]:
    """Feature values for one accepted sample; nulls pass through unimputed."""
    values: dict[str, Any] = {"pdp_source_row_number": sample["source_row_number"],
                              "pdp_sample_id": sample["sample_pk"]}
    for source_column, spec in PRODUCT_CONTEXT_COLUMNS.items():
        value = sample[source_column]
        if value is None:
            values[spec["feature"]] = None
        elif isinstance(value, str):
            values[spec["feature"]] = value
        elif isinstance(value, int) and spec["datatype"] == "integer":
            if value < 0:
                raise ValueError("negative sample-unit count")
            values[spec["feature"]] = value
        else:
            raise ValueError("unexpected feature value type for " + spec["feature"])
    collection = sample["collection_date"]
    if not isinstance(collection, date):
        raise ValueError("collection_date must carry its declared date type")
    values.update(compute_calendar(collection))
    return values


def stream_feature_rows(samples_path: Path) -> Iterator[dict[str, Any]]:
    for sample in read_table(samples_path):
        yield assemble_row(sample)


def output_hashes(directory: Path) -> dict[str, dict[str, Any]]:
    return {p.relative_to(directory).as_posix(): {"sha256": sha256_file(p), "size_bytes": p.stat().st_size}
            for p in sorted(directory.rglob("*")) if p.is_file()}


def build_schema(contract: dict, scope: dict, cutoff: str) -> dict[str, Any]:
    table = contract["tables"][SOURCE_TABLE]
    columns: dict[str, dict[str, Any]] = {
        "pdp_source_row_number": {"datatype": "integer", "role": "lineage", "source_column": "source_row_number",
                                  "note": "M2 lineage; not a predictor"},
        "pdp_sample_id": {"datatype": "string", "role": "lineage", "source_column": "sample_pk",
                          "note": "Release-local grouping key; a lineage column, never a predictor"},
    }
    for spec in feature_columns():
        entry: dict[str, Any] = {"datatype": spec["datatype"], "role": "feature",
                                 "source_column": spec["source_column"], "family": spec["family"],
                                 "unit": spec["unit"], "derivation": spec["derivation"]}
        if spec["source_column"] in PRODUCT_CONTEXT_COLUMNS:
            entry["canonical_source_field"] = table["fields"][spec["source_column"]]["canonical_name"]
        columns[spec["feature"]] = entry
    decision = scope["decision_contract"]
    return {
        "status": "NOT MODEL-READY",
        "milestone": "M5",
        "table": FEATURE_TABLE,
        "row_granularity": "one feature row per accepted M2 PDP 2024 sample record",
        "source": {**table["source"], "source_table": table["source_table"]},
        "columns": columns,
        "null_encoding": {"null": "\\N", "empty_string": "non-null empty string",
                          "escape": "Prefix an extra backslash to every non-null value starting with a backslash"},
        "prediction_context": {
            "experiment_definition": decision["experiment_definition"],
            "prediction_cutoff": cutoff,
            "prediction_cutoff_precision": decision["prediction_cutoff_precision"],
            "availability_evidence": {
                "source": decision["availability_evidence"]["source"],
                "url": decision["availability_evidence"]["url"],
                "quoted_text": decision["availability_evidence"]["quoted_text"],
                "fetched_at_utc": decision["availability_evidence"]["fetched_at_utc"],
                "evidence_path": decision["availability_evidence"]["evidence_path"],
                "evidence_sha256": decision["availability_evidence"]["evidence_sha256"]},
        },
        "not_performed": ["cross-source joins", "label creation", "missingness-indicator features",
                          "model training", "M6 enrichment", "M7 leakage audit", "M8 modeling handoff"],
    }


def summarize(contract: dict, scope: dict, cutoff: str, samples_table: dict, samples_path: Path, root: Path,
              output: Path, row_count: int, nulls: dict[str, int]) -> dict[str, Any]:
    schema = build_schema(contract, scope, cutoff)
    context = schema["prediction_context"]
    return {
        "milestone": "M5", "status": "PARTIAL", "data_status": "NOT MODEL-READY",
        "materialized_families": list(TARGET_FAMILIES),
        "features_emitted": len(feature_columns()), "feature_tables_written": 1,
        "labels_created": 0, "joins_performed": 0, "clean_rows": row_count,
        "m2_samples_clean_rows": samples_table["clean_rows"],
        "prediction_cutoff": cutoff,
        "prediction_cutoff_precision": context["prediction_cutoff_precision"],
        "experiment_definition": context["experiment_definition"],
        "m5_evidence": {"pdp_2024_archive_posting": dict(context["availability_evidence"])},
        "feature_null_counts": dict(sorted(nulls.items())),
        "features": feature_columns(),
        "lineage_columns": list(LINEAGE_COLUMNS),
        "artifacts": {
            "output_directory": output.relative_to(root).as_posix(),
            "outputs": output_hashes(output),
            "m2_samples_input": {"path": samples_path.relative_to(root).as_posix(),
                                 "sha256": sha256_file(samples_path)},
        },
        "not_performed": list(schema["not_performed"]),
    }


def check_report_paths(root: Path, summary_path: Path, report_path: Path) -> None:
    reports = (root / "reports").resolve()
    for path in (summary_path, report_path):
        if not path.resolve().is_relative_to(reports) or not path.name.startswith("m5_"):
            raise ValueError("M5 generated reports must stay in reports/ with the m5_ prefix")


def verify_outputs(output: Path, summary_file: Path) -> dict[str, Any]:
    """Independent typed readback of the written feature table against its pinned summary."""
    if not summary_file.exists():
        raise ValueError("M5 pinned summary is missing; nothing to verify")
    summary = json.loads(summary_file.read_text())
    if output_hashes(output) != summary["artifacts"]["outputs"]:
        raise ValueError("M5 feature table bytes differ from their pinned summary")
    read_rows = 0
    for row in read_table(output / (FEATURE_TABLE + ".csv")):
        read_rows += 1
        if row["pdp_source_row_number"] is None or row["pdp_sample_id"] is None:
            raise ValueError("lineage values must never be null")
        for name in feature_names():
            if row[name] is None and name not in FEATURE_NULLABLE:
                raise ValueError("unexpected null in a non-null feature: " + name)
    if read_rows != summary["clean_rows"] or summary["clean_rows"] != summary["m2_samples_clean_rows"]:
        raise ValueError("M5 readback row count differs from the summary")
    return {"status": summary["status"], "rows": read_rows, "features": summary["features_emitted"],
            "output_directory": summary["artifacts"]["output_directory"],
            "null_counts": summary["feature_null_counts"]}


def materialize(root: Path, output_directory: str = DEFAULT_OUTPUT_DIRECTORY,
                summary_path: str = DEFAULT_SUMMARY_PATH, report_path: str = DEFAULT_REPORT_PATH,
                verify_only: bool = False) -> dict[str, Any]:
    root = root.resolve()
    output = inside_root(root, output_directory)
    interim = root / "data" / "interim"
    if not output.resolve().is_relative_to(interim.resolve()) or output.resolve() == interim.resolve():
        raise ValueError("M5 feature tables must live in a subdirectory of data/interim")
    summary_file = inside_root(root, summary_path)
    report_file = inside_root(root, report_path)
    check_report_paths(root, summary_file, report_file)

    contract, scope, _assessment = load_assessment(root)
    samples_path, samples_table = verify_m2_samples(root)
    cutoff = scope["decision_contract"]["prediction_cutoff"]
    if verify_only:
        return verify_outputs(output, summary_file)

    csv_path = output / (FEATURE_TABLE + ".csv")
    schema_path = output / (FEATURE_TABLE + ".schema.json")
    existing_files = sorted(p.name for p in output.rglob("*") if p.is_file()) if output.exists() else []
    if existing_files:
        if set(existing_files) != {FEATURE_TABLE + ".csv", FEATURE_TABLE + ".schema.json"}:
            raise ValueError("Existing M5 output directory holds unrelated content; refusing to overwrite")
        pinned = json.loads(summary_file.read_text()) if summary_file.exists() else None
        if pinned is None or pinned["artifacts"]["output_directory"] != output.relative_to(root).as_posix():
            raise ValueError("Existing M5 output directory has no matching pinned summary; refusing to overwrite")
        if output_hashes(output) != pinned["artifacts"]["outputs"]:
            raise ValueError("Existing M5 feature outputs differ from their pinned summary; refusing to overwrite")
        return verify_outputs(output, summary_file)

    with tempfile.TemporaryDirectory(dir=interim, prefix=".m5-stage-") as temporary:
        stage = Path(temporary)
        columns = [LINEAGE_COLUMNS[0], LINEAGE_COLUMNS[1], *feature_names()]
        nulls: dict[str, int] = {}
        row_count = 0
        seen_sample_ids: set[str] = set()
        with (stage / (FEATURE_TABLE + ".csv")).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(columns)
            for record in stream_feature_rows(samples_path):
                if set(record) != set(columns):
                    raise ValueError("feature record columns differ from the declared schema")
                if record["pdp_sample_id"] in seen_sample_ids:
                    raise ValueError("duplicate feature key pdp_sample_id")
                seen_sample_ids.add(record["pdp_sample_id"])
                for name in feature_names():
                    if record[name] is None:
                        nulls[name] = nulls.get(name, 0) + 1
                writer.writerow(encode(record[name]) for name in columns)
                row_count += 1
        if row_count != samples_table["clean_rows"]:
            raise ValueError("feature row count differs from the pinned M2 samples table")
        (stage / (FEATURE_TABLE + ".schema.json")).write_text(
            json.dumps(build_schema(contract, scope, cutoff), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        staged = output_hashes(stage)
        if set(staged) != {FEATURE_TABLE + ".csv", FEATURE_TABLE + ".schema.json"}:
            raise ValueError("staged M5 output names differ from the declared table artifacts")
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        if csv_path.exists() or schema_path.exists():
            raise ValueError("M5 feature outputs appeared during staging; refusing to overwrite")
        os.replace(stage / (FEATURE_TABLE + ".csv"), csv_path)
        os.replace(stage / (FEATURE_TABLE + ".schema.json"), schema_path)
        outputs = output_hashes(output)
        if outputs != {name: staged[name] for name in outputs}:
            raise ValueError("M5 published outputs differ from their staged, hashed bytes")

    summary = summarize(contract, scope, cutoff, samples_table, samples_path, root, output, row_count, nulls)
    summary_file.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_file.write_text(render_report(summary), encoding="utf-8")
    return {"status": summary["status"], "rows": row_count, "features": len(feature_columns()),
            "output_directory": summary["artifacts"]["output_directory"],
            "outputs": outputs, "null_counts": dict(sorted(nulls.items()))}


def feature_hashes(cutoff: str) -> dict[str, str]:
    return {FEATURE_TABLE + ".csv": "data", FEATURE_TABLE + ".schema.json": "schema"}


def render_report(summary: dict[str, Any]) -> str:
    artifact = summary["artifacts"]
    evidence = summary["m5_evidence"]["pdp_2024_archive_posting"]
    lines = ["# M5 — PDP sample-context feature materialization", "",
             "**NOT MODEL-READY. Source-specific, un-joined, unlabeled M5 feature table only.** The table is not a "
             "training design, and this report is not the M7 leakage audit.", "",
             "Families materialized: **" + ", ".join("`" + name + "`" for name in summary["materialized_families"]) +
             "**. All other M5 families remain blocked and were not touched.", "",
             f"- Experiment: {summary['experiment_definition']}",
             f"- Prediction cutoff: **{summary['prediction_cutoff']}** (precision: "
             f"{summary['prediction_cutoff_precision']})",
             f"- Availability evidence: {evidence['source']} — “{evidence['quoted_text']}” "
             f"(evidence: `{evidence['evidence_path']}`, retrieved {evidence['fetched_at_utc']})", "",
             "## What was read", "",
             f"- Single pinned M2 table: `{summary['artifacts']['m2_samples_input']['path']}` only "
             f"({summary['clean_rows']:,} accepted rows; SHA-256 "
             f"`{summary['artifacts']['m2_samples_input']['sha256']}` pinned against "
             "`reports/m2_cleaning_summary.json` before reading).",
             "- `usda_pdp.results` analytical fields were never read; no other source table was consulted.", "",
             "## What was written", "",
             f"Directory `{artifact['output_directory']}`; {summary['feature_tables_written']} table, "
             f"{summary['features_emitted']} feature columns (lineage columns excluded from the count).", "",
             "| Column | Source input | Family | Datatype | Unit / derivation |", "| --- | --- | --- | --- | --- |"]
    for column in summary["features"]:
        lines.append(f"| `{column['feature']}` | usda_pdp.samples / {column['source_column']} | "
                     f"{column['family']} | {column['datatype']} | {column['unit']}: {column['derivation']} |")
    lines += ["",
              "Null passthrough counts follow the pinned M2 missingness (no imputation anywhere):",
              "`" + json.dumps(summary["feature_null_counts"], sort_keys=True) + "`.",
              "Lineage columns retained for traceability but excluded from the feature count: "
              "`" + ", ".join(summary["lineage_columns"]) + "`.", "",
              "## Output checksums", "", "| Relative to output directory | Bytes | SHA-256 |", "| --- | ---: | --- |"]
    lines += [f"| `{name}` | {spec['size_bytes']:,} | `{spec['sha256']}`"
              for name, spec in sorted(artifact["outputs"].items())]
    lines += ["", "## Not performed", "", "Explicit under this materialization:", ""]
    lines += ["- " + item for item in summary["not_performed"]]
    lines += [
        "- The `pdp_input_missingness` family stayed blocked (`MISSINGNESS_SEMANTICS_POLICY_UNDEFINED` plus "
        "unverified `growst`/`packst` field availability), so no missingness-indicator feature was emitted.",
        "- The M2 year/month/day components were not repackaged as new features; the three calendar features are "
        "deterministic derivations of `pdp_collection_date` only.",
        "- Native codes pass through verbatim; no cross-source taxonomy, decoding, entity crosswalk or scoring was applied.",
        "",
        "## Reproduce", "",
        "`PYTHONPATH=src python -m tracefront_data.pdp_sample_context_features` "
        "(or add `--verify-only` to re-check existing outputs against the pinned summary). "
        "The prerequisite assessment is re-executed first: "
        "`PYTHONPATH=src python -m tracefront_data.feature_readiness`. Python standard library only.", "",
        "Person B may inspect this table as a source-specific M5 provenance feature layer with a documented "
        "prediction cutoff; it is not an approved model-ready matrix, and the eventual use of native codes as "
        "predictors stays subject to later review.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true",
                        help="re-check existing outputs against the pinned summary")
    args = parser.parse_args()
    root = Path.cwd()
    result = materialize(root, verify_only=args.verify_only)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
