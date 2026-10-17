"""M2 cleaning for M1-eligible sources only. All outputs are NOT MODEL-READY."""

from __future__ import annotations

import argparse
from datetime import date
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any
from collections import Counter
from decimal import Decimal

from tracefront_data.audit import sha256_file
from tracefront_data.cleaning.context import clean_openfda, clean_opendosm
from tracefront_data.cleaning.pdp import clean_pdp
from tracefront_data.cleaning.weather import clean_noaa
from tracefront_data.cleaning.common import read_table
from tracefront_data.provenance import inside_root, verify_manifest

LOG = logging.getLogger(__name__)
SUPPORTED = {"usda_pdp", "openfda_enforcement", "noaa_ghcn_daily", "opendosm_crops_state",
             "opendosm_crops_district_production", "opendosm_crops_district_area"}


def verify_baseline(root: Path, source_manifest: Path) -> tuple[dict, dict]:
    sources = json.loads(source_manifest.read_text())
    receipt_path = inside_root(root, sources["receipt"])
    if sha256_file(receipt_path) != sources["receipt_sha256"]:
        raise ValueError("Frozen M1 receipt hash mismatch; no M2 processing permitted")
    receipt = json.loads(receipt_path.read_text())
    verification = verify_manifest(root, receipt)
    if not verification["integrity_ok"]:
        raise ValueError(f"Frozen M1 raw artifact integrity failed: {verification}")
    for name, source in sources["datasets"].items():
        if source.get("m2_eligible") is not True:
            continue
        expected = {a["artifact_id"]: a for a in receipt["datasets"][name]["artifacts"] if a["status"] == "captured"}
        for artifact in source["artifacts"]:
            if artifact["status"] == "captured":
                original = expected[artifact["artifact_id"]]
                if any(artifact[k] != original[k] for k in ("path", "sha256", "size_bytes")):
                    raise ValueError("Source manifest artifact differs from frozen M1 receipt")
    return sources, verification


def output_hashes(directory: Path) -> dict[str, dict[str, Any]]:
    return {p.relative_to(directory).as_posix(): {"sha256": sha256_file(p), "size_bytes": p.stat().st_size}
            for p in sorted(directory.rglob("*")) if p.is_file()}


def run_cleaning(root: Path, source_manifest: Path, output_directory: Path) -> dict:
    root = root.resolve()
    sources, before = verify_baseline(root, source_manifest)
    eligible = {k: v for k, v in sources["datasets"].items() if v.get("m2_eligible") is True}
    if not eligible or eligible.keys() - SUPPORTED:
        raise ValueError("No eligible sources or an eligible source has no reviewed M2 cleaner")
    output_directory = inside_root(root, output_directory.as_posix())
    interim = root / "data/interim"
    if not output_directory.resolve().is_relative_to(interim.resolve()) or output_directory.resolve() == interim.resolve():
        raise ValueError("M2 outputs must be a new directory below data/interim, never the raw layer")
    interim.mkdir(parents=True, exist_ok=True)
    cutoff = date.fromisoformat(sources["receipt_created_at"][:10])
    results = {}
    with tempfile.TemporaryDirectory(dir=interim, prefix=".m2-stage-") as temporary:
        stage = Path(temporary) / "tables"
        stage.mkdir()
        scratch = Path(temporary) / "scratch"
        scratch.mkdir()
        for name, source in sorted(eligible.items()):
            LOG.info("Cleaning eligible source %s", name)
            captured = {a["artifact_id"]: a for a in source["artifacts"] if a["status"] == "captured"}
            data_artifacts = [a for a in captured.values() if a["role"] in {"data", "context_data"}]
            metadata = {"source_entry": name, "publisher": source["publisher"],
                        "canonical_source_url": source["canonical_source_url"], "license": source["license"],
                        "intended_ml_role": source["intended_ml_role"],
                        "contamination_domain": source["contamination_domain"],
                        "artifacts": [{k: a.get(k) for k in ("path", "sha256", "source_url", "retrieved_at")}
                                      for a in data_artifacts]}
            directory = stage / ({"openfda_enforcement": "openfda", "noaa_ghcn_daily": "noaa"}.get(name, name))
            def artifact_path(artifact_id: str) -> Path:
                return inside_root(root, captured[artifact_id]["path"])
            if name == "usda_pdp":
                result = clean_pdp(artifact_path("pdp_2024"), directory,
                                   source["inspection"]["dictionary_mapping"], cutoff, metadata, scratch)
                for table in ("samples", "results"):
                    if result["tables"][table]["raw_rows"] != source["inspection"]["sample_table" if table == "samples" else "result_table"]["rows"]:
                        raise ValueError("PDP raw count differs from frozen M1 inspection")
            elif name == "openfda_enforcement":
                result = clean_openfda(artifact_path("openfda_local_json"), directory,
                                       source["inspection"]["columns"], cutoff, metadata)
                if result["tables"]["recalls"]["raw_rows"] != source["inspection"]["rows"]:
                    raise ValueError("openFDA raw count differs from frozen M1 inspection")
            elif name == "noaa_ghcn_daily":
                result = clean_noaa(artifact_path("ghcn_station_data"), directory, cutoff, metadata)
                if result["monthly_input_accounting"]["raw_rows"] != source["inspection"]["rows"]:
                    raise ValueError("NOAA raw count differs from frozen M1 inspection")
            else:
                table = name.removeprefix("opendosm_")
                result = clean_opendosm(artifact_path(table), directory, table,
                                        source["inspection"]["columns"], cutoff, metadata)
                if result["tables"][table]["raw_rows"] != source["inspection"]["rows"]:
                    raise ValueError("OpenDOSM raw count differs from frozen M1 inspection")
            result["output_subdirectory"] = directory.relative_to(stage).as_posix()
            result["intended_ml_role"] = source["intended_ml_role"]
            results[name] = result
        (stage / "README.md").write_text(
            "# M2 source-specific tables — NOT MODEL-READY\n\n"
            "Separate source tables only. CSV datatypes, units and null/escape conventions are in *.schema.json.\n"
            "Use tracefront_data.cleaning.common.read_table to read declared datatypes without a dataframe engine.\n"
            "Rejected rows and issues retain source-row evidence. No imputation, features, joins or invented risk labels.\n"
            "EDA, canonical contracts, features, enrichment and leakage audits remain pending.\n")
        outputs = output_hashes(stage)
        _, after = verify_baseline(root, source_manifest)
        if before != after:
            raise ValueError("M1 verification changed during cleaning")
        if output_directory.exists():
            if output_hashes(output_directory) != outputs:
                raise ValueError("Existing M2 outputs differ; refusing to overwrite. Use a new output directory")
        else:
            output_directory.parent.mkdir(parents=True, exist_ok=True)
            os.rename(stage, output_directory)
    code = [Path(__file__), *sorted((Path(__file__).parent / "cleaning").glob("*.py"))]
    return {"milestone": "M2", "status": "COMPLETE", "data_status": "NOT MODEL-READY",
            "source_manifest": source_manifest.relative_to(root).as_posix(),
            "source_manifest_sha256": sha256_file(source_manifest), "m1_receipt": sources["receipt"],
            "m1_receipt_sha256": sources["receipt_sha256"], "frozen_date_cutoff": cutoff.isoformat(),
            "raw_integrity_before": before, "raw_integrity_after": after,
            "cleaning_code_sha256": {p.relative_to(Path(__file__).parent).as_posix(): sha256_file(p) for p in code},
            "skipped_ineligible_sources": sorted(sources["datasets"].keys() - eligible.keys()),
            "sources": results, "output_directory": output_directory.relative_to(root).as_posix(), "outputs": outputs,
            "statistics_notes": ["Before missingness counts lexical blank/null source fields; some blanks are documented defaults, not unknown",
                                 "After missingness counts explicit nulls among accepted rows only",
                                 "Rejection reason counts can overlap; row totals are unique records",
                                 "NOAA raw monthly rows expand to calendar-day element records; padding is accounted separately"],
            "s390x_executed": False, "third_party_runtime_dependencies": []}


def write_report(summary: dict, path: Path) -> None:
    lines = ["# M2 — Cleaning and standardization", "", "**NOT MODEL-READY.** Eligible-cohort cleaning status: " + summary["status"] + ".",
             "", "Source tables remain independent. No models, predictive features, cross-source joins, imputation or contamination/exceedance labels were created.",
             "", "| Source / table | Raw input records | Clean records | Rejected | Duplicates |", "| --- | ---: | ---: | ---: | ---: |"]
    for source, result in summary["sources"].items():
        for table, stats in result["tables"].items():
            lines.append(f"| {source} / {table} | {stats['raw_rows']:,} | {stats['clean_rows']:,} | {stats['rejected_rows']:,} | {stats['duplicate_rows']:,} |")
    for source, result in summary["sources"].items():
        lines += ["", "## " + source, "", "Output: `" + summary["output_directory"] + "/" + result["output_subdirectory"] + "`. Role: " + result["intended_ml_role"] + "."]
        if "duplicate_definition" in result:
            lines += ["", "Duplicate count definition: " + result["duplicate_definition"] + "."]
        if "conflicting_key_groups" in result:
            lines += ["", "Conflicting natural-key groups quarantined in full: " + str(result["conflicting_key_groups"]) + "."]
        lines += ["", "Known ambiguities:", ""] + ["- " + item for item in result.get("known_ambiguities", [])]
        if "monthly_input_accounting" in result:
            lines += ["", "NOAA monthly input accounting: `" + json.dumps(result["monthly_input_accounting"], sort_keys=True) + "`.",
                      "Excluded noncalendar sentinel padding slots: " + str(result["excluded_noncalendar_padding_slots"]) + ". Raw table count above refers to calendar-day slots, not original monthly lines."]
        for name, stats in result["tables"].items():
            lines += ["", "### " + name, "", "- Grain: " + stats["row_granularity"],
                      "- Missing critical identifiers: " + str(stats["missing_critical_identifiers"]),
                      "- Malformed rows: " + str(stats["malformed_rows"]),
                      "- Invalid numeric rows: " + str(stats["invalid_numeric_rows"]),
                      "- Invalid date rows: " + str(stats["invalid_date_rows"]),
                      "- Rejection reasons: `" + json.dumps(stats["rejection_reasons"], sort_keys=True) + "`",
                      "- Quality issue counts: `" + json.dumps(stats["quality_issue_counts"], sort_keys=True) + "`",
                      "- Missingness before: `" + json.dumps(stats["missingness_before"], sort_keys=True) + "`",
                      "- Missingness after: `" + json.dumps(stats["missingness_after"], sort_keys=True) + "`", "", "Transformations:", ""]
            lines += ["- " + t for t in stats["transformations"]]
            lines += ["", "Preserved missingness semantics:", ""] + ["- " + t for t in stats["missingness_semantics"]]
            if "preserved_mean_code_counts" in stats:
                lines += ["", "Preserved MEAN counts: `" + json.dumps(stats["preserved_mean_code_counts"], sort_keys=True) + "`"]
    lines += ["", "## Output checksums", "", "| Relative to output directory | Bytes | SHA-256 |", "| --- | ---: | --- |"]
    lines += [f"| `{name}` | {value['size_bytes']:,} | `{value['sha256']}` |" for name, value in summary["outputs"].items()]
    lines += ["", "## Limits and handoff", "", "- " + "\n- ".join(summary["statistics_notes"]),
              "- IDs and source-row references are lineage/grouping metadata, not approved predictors.",
              "- Analytical CONCEN/MEAN/ANNOTATE, recall status/reason/termination, and quality metadata are not approved predictors or universal contamination labels.",
              "- Literal free-text N/A/Na tokens are retained unless a field dictionary explicitly defines them; missing reasons can remain ambiguous.",
              "- NOAA flagged values remain visible; M3 must inspect quality before later weather features. Daily reporting dates have unknown availability/timezone semantics.",
              "- OpenDOSM reference_date/year is annual context, not publication time; national/state totals must not be blindly summed.",
              "- Later EDA, canonical schema, features, enrichment and leakage audits are required before modeling.",
              "- Python 3.11+ standard library only. sqlite3 provides temporary disk-backed exact-result duplicate detection; target Python must include SQLite support. No new PyPI/native package installed.",
              "- Source manifest and cleaning-code hashes, output hashes and before/after raw integrity checks are in m2_cleaning_summary.json; reproducibility/test evidence is in m2_validation.json.",
              "- Pending FSIS and FDA inspection source entries were not cleaned. Person B code, raw artifacts and frozen M1 reports/receipts remain unchanged."]
    path.write_text("\n".join(lines) + "\n")


def verify_cleaned(root: Path, summary: dict) -> dict:
    """Independent streaming readback of every typed output and source reference."""
    output_directory = inside_root(root, summary["output_directory"])
    if output_hashes(output_directory) != summary["outputs"]:
        raise ValueError("M2 output bytes differ from their pinned summary")
    source_manifest = inside_root(root, summary.get("source_manifest", "reports/m1_source_manifest.json"))
    if sha256_file(source_manifest) != summary["source_manifest_sha256"]:
        raise ValueError("M1 source manifest differs from M2 provenance")
    _, raw_integrity = verify_baseline(root, source_manifest)
    sample_ids = set()
    counts = {}
    # Samples first for same-source referential validation; nothing is joined.
    ordered = sorted(summary["sources"].items(), key=lambda item: item[0] != "usda_pdp")
    for source_name, source in ordered:
        directory = output_directory / source["output_subdirectory"]
        for table_name, table in sorted(source["tables"].items(), key=lambda item: item[0] != "samples"):
            count = 0
            missing = Counter()
            mean_codes = Counter()
            flags = {name: Counter() for name in ("measurement_flag", "quality_flag", "source_flag")}
            seen_keys = set()
            for row in read_table(directory / (table_name + ".csv")):
                count += 1
                missing.update(k for k, value in row.items() if value is None)
                if {"contaminated", "contamination_label", "pesticide_exceedance", "supplier_risk"} & row.keys():
                    raise ValueError("Unapproved derived label/risk column")
                if any(isinstance(v, Decimal) and not v.is_finite() for v in row.values()):
                    raise ValueError("Nonfinite decimal in clean output")
                if source_name == "usda_pdp":
                    if table_name == "samples":
                        if row["sample_pk"] in sample_ids:
                            raise ValueError("Duplicate clean PDP sample key")
                        sample_ids.add(row["sample_pk"])
                    else:
                        if row["sample_pk"] not in sample_ids:
                            raise ValueError("Clean analytical record has no accepted sample")
                        mean_codes[row["mean"]] += 1
                        if row["mean"] in {"ND", "NP"} and row["concen"] is None and row["concen_missing_reason"] != "censored_" + row["mean"]:
                            raise ValueError("Lost nondetect quality/censoring distinction")
                elif source_name == "noaa_ghcn_daily":
                    expected_value = None if row["raw_value"] == -9999 else Decimal(row["raw_value"]) / Decimal(10)
                    if row["value"] != expected_value:
                        raise ValueError("Weather scaling/sentinel mismatch")
                    for name in flags:
                        if len(row[name]) != 1:
                            raise ValueError("Weather flag character lost")
                        flags[name][row[name]] += 1
                elif source_name.startswith("opendosm_"):
                    reference = row["reference_date"]
                    if (reference.month, reference.day) != (1, 1) or reference.year != row["reference_year"]:
                        raise ValueError("Annual reference-date semantics lost")
                if source_name != "usda_pdp" or table_name == "samples":
                    key = (row["recall_number"],) if source_name == "openfda_enforcement" else (
                        (row["station_id"], row["observation_date"], row["element"]) if source_name == "noaa_ghcn_daily" else (
                        (row["reference_date"], row["state"], row.get("district"), row["crop_type"], row.get("crop_species"))
                        if source_name.startswith("opendosm_") else (row["sample_pk"],)))
                    if key in seen_keys:
                        raise ValueError("Duplicate clean natural key")
                    seen_keys.add(key)
            if count != table["clean_rows"] or dict(sorted(missing.items())) != table["missingness_after"]:
                raise ValueError("Readback row/missingness counts differ from summary")
            rejected_path = directory / (table_name + ".rejected.jsonl")
            with rejected_path.open() as stream:
                rejections = sum(1 for line in stream if json.loads(line))
            if rejections != table["rejected_rows"]:
                raise ValueError("Rejection ledger count differs from summary")
            if table_name == "results" and dict(sorted(mean_codes.items())) != table["preserved_mean_code_counts"]:
                raise ValueError("Analytical code counts changed")
            if source_name == "noaa_ghcn_daily" and {k: dict(sorted(v.items())) for k, v in flags.items()} != source["preserved_flag_counts"]:
                raise ValueError("Weather flag counts changed")
            counts[source_name + "/" + table_name] = count
    return {"integrity_ok": True, "typed_tables_read": len(counts), "accepted_row_counts": counts,
            "output_files_checked": len(summary["outputs"]), "raw_integrity": raw_integrity,
            "same_source_pdp_references_valid": True, "no_cross_source_joins": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", default="reports/m1_source_manifest.json")
    parser.add_argument("--output-dir", default="data/interim/m2_v1")
    parser.add_argument("--summary", default="reports/m2_cleaning_summary.json")
    parser.add_argument("--report", default="reports/m2_cleaning_report.md")
    parser.add_argument("--verify-only", action="store_true", help="Hash and stream-read existing M2 outputs without cleaning")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    root = Path.cwd()
    summary_path, report_path = inside_root(root, args.summary), inside_root(root, args.report)
    for path in (summary_path, report_path):
        if not path.resolve().is_relative_to((root / "reports").resolve()) or not path.name.startswith("m2_"):
            raise ValueError("Generated M2 reports must stay in reports/m2_*; frozen M1 reports cannot be overwritten")
    if args.verify_only:
        print(json.dumps(verify_cleaned(root, json.loads(summary_path.read_text())), indent=2))
        return
    summary = run_cleaning(root, inside_root(root, args.source_manifest), Path(args.output_dir))
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    write_report(summary, report_path)
    LOG.info("M2 eligible-cohort cleaning complete. Outputs are NOT MODEL-READY")


if __name__ == "__main__":
    main()
