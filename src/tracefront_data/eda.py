"""M3: read-only, source-specific profiles of verified M2 tables (stdlib only).

Run: PYTHONPATH=src python -m tracefront_data.eda
No sampled rows, source joins, imputation, new labels or modeling are used.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from html import escape
import json
import logging
from pathlib import Path
import re
from typing import Any, Iterable

from tracefront_data.audit import sha256_file
from tracefront_data.clean import output_hashes, verify_baseline, verify_cleaned
from tracefront_data.cleaning.common import read_table
from tracefront_data.provenance import inside_root

LOG = logging.getLogger(__name__)
CAP = 10000
FREE_TEXT = {"address_1", "address_2", "code_info", "more_code_info", "product_description",
             "product_quantity", "reason_for_recall", "distribution_pattern", "concen_raw"}
MEANINGS = {"ND": "Non-detect: validated, well-recovered",
            "NP": "Non-detect: marginal performing analyte",
            "O": "Detect: original extraction value", "R": "Detect: re-extraction analysis value"}
WARNINGS = {
    "usda_pdp": ["Assay counts are not independent sample counts or population contamination rates.",
                 "ND and NP are distinct nondetect codes, not zeros. LOD varies by assay.",
                 "O/R and publisher annotations are analytical outcomes, not approved predictors.",
                 "Publisher presumptive-violation annotation codes do not establish an independently validated exceedance label.",
                 "Collection date does not prove result/publication availability; sample IDs and lab codes require leakage review."],
    "noaa_ghcn_daily": ["One Malaysian station is not national spatial coverage.",
                        "Absent calendar slots and -9999 missing values have different denominators.",
                        "Blank quality flag means no failed check recorded, not guaranteed validity.",
                        "Yearly counts audit coverage only; no rolling weather features are computed.",
                        "Daily reference dates do not establish historical public availability."],
    "openfda_enforcement": ["All records describe recalls; there is no tested-negative comparison population.",
                           "Classification/status frequencies are contextual, not contamination class balance.",
                           "event_id may repeat across product-specific recalls; firm strings are not verified entity IDs.",
                           "Status, reason, classification and termination can reveal retrospective outcomes.",
                           "Snapshot registration does not recover its original download URL/time or historical field versions."],
    "opendosm": ["Annual reference markers are not publication timestamps; district coverage is 2017 only.",
                 "Missing district/crop combinations are not measured zeros.",
                 "National/state totals overlap; neither are blindly summed here.",
                 "Conflicting key versions remain quarantined; undocumented strata or publisher duplication remain unresolved.",
                 "Production/area context is not food contamination ground truth."],
}


def token(value: Any) -> str:
    if value is None:
        return "<NULL>"
    if value == "":
        return "<EMPTY>"
    if isinstance(value, str) and value.isspace():
        return "<BLANK>"
    return str(value)


def ranked(counts: Counter, limit: int = 20) -> list[dict]:
    return [{"value": str(k), "count": v} for k, v in sorted(counts.items(), key=lambda x: (-x[1], str(x[0])))[:limit]]


class Numeric:
    """Exact weighted summaries; cap distinct values rather than sampling silently."""

    def __init__(self, cap: int = CAP):
        self.cap = cap
        self.count = self.zero = self.negative = 0
        self.minimum: Decimal | None = None
        self.maximum: Decimal | None = None
        self.total = Decimal(0)
        self.counts: Counter | None = Counter()

    def add(self, value: Any) -> None:
        number = Decimal(value)
        if not number.is_finite():
            raise ValueError("Nonfinite number in M2 input")
        self.count += 1
        self.zero += number == 0
        self.negative += number < 0
        self.minimum = number if self.minimum is None else min(self.minimum, number)
        self.maximum = number if self.maximum is None else max(self.maximum, number)
        self.total += number
        if self.counts is not None:
            self.counts[number] += 1
            if len(self.counts) > self.cap:
                self.counts = None

    def finish(self) -> dict:
        out = {"count": self.count, "zero_count": self.zero, "negative_count": self.negative,
               "min": str(self.minimum) if self.count else None,
               "max": str(self.maximum) if self.count else None,
               "mean": str(self.total / self.count) if self.count else None,
               "quantile_method": "Exact nearest-rank, among nonnull values; no interpolation",
               "quantiles": None, "histogram": None}
        if not self.count or self.counts is None:
            out["distribution_status"] = "empty" if not self.count else "distinct-value cap exceeded; no sampled estimate"
            return out
        ordered = sorted(self.counts.items())
        quantiles = {}
        for name, percent in (("p25", 25), ("p50", 50), ("p75", 75), ("p95", 95), ("p99", 99)):
            rank = max(1, (self.count * percent + 99) // 100)
            cumulative = 0
            for number, count in ordered:
                cumulative += count
                if cumulative >= rank:
                    quantiles[name] = str(number)
                    break
        bins = [0] * (1 if self.minimum == self.maximum else 10)
        width = (self.maximum - self.minimum) / len(bins)
        for number, count in ordered:
            index = 0 if not width else min(9, int((number - self.minimum) / width))
            bins[index] += count
        out.update(quantiles=quantiles, distribution_status="exact", histogram=[
            {"lower": str(self.minimum + width * i), "upper": str(self.minimum + width * (i + 1)),
             "upper_inclusive": i == len(bins) - 1, "count": count} for i, count in enumerate(bins)])
        return out


def profile_table(rows: Iterable[dict], schema: dict, source: str, table: str) -> dict:
    columns = schema["columns"]
    nulls, empty, markers = Counter(), Counter(), Counter()
    categories = {k: Counter() for k, v in columns.items()
                  if v["datatype"] == "string" and k not in FREE_TEXT}
    overflow = set()
    dates = {}
    numeric: dict[str, Numeric] = {}
    special: dict[str, Any] = {}
    code_commodity, code_unit, code_concen, annotations = Counter(), Counter(), Counter(), Counter()
    sample_assays, detection_groups = Counter(), defaultdict(Counter)
    weather, weather_year = {}, {}
    date_order = Counter()
    date_examples = []
    country_by_origin = Counter()
    n = 0
    for row in rows:
        n += 1
        for name, value in row.items():
            if value is None:
                nulls[name] += 1
                continue
            if value == "":
                empty[name] += 1
            if isinstance(value, str) and value.strip().lower() in {"n/a", "na", "unknown", "not applicable"}:
                markers[name] += 1
            spec = columns[name]
            kind = spec["datatype"]
            if name in categories and name not in overflow:
                categories[name][token(value)] += 1
                if len(categories[name]) > CAP:
                    categories[name].clear()
                    overflow.add(name)
            if kind == "date":
                d = dates.setdefault(name, {"min": value.isoformat(), "max": value.isoformat(), "by_month": Counter()})
                d["min"] = min(d["min"], value.isoformat())
                d["max"] = max(d["max"], value.isoformat())
                d["by_month"][value.isoformat()[:7]] += 1
            if kind in {"integer", "decimal"} and spec.get("role") != "lineage" and name not in {
                "source_day_of_month", "raw_value", "year", "month", "day", "reference_year"
            }:
                # Never pool numeric concentrations/LODs or weather elements across units.
                partition = token(row.get(spec["unit_column"])) if spec.get("unit_column") else spec.get("unit", "unspecified")
                if source == "noaa_ghcn_daily" and name == "value":
                    partition = row["element"] + "/" + row["unit"] + "/" + row["observation_status"]
                key = name + " [" + partition + "]"
                if key not in numeric:
                    numeric[key] = Numeric()
                numeric[key].add(value)
        if source == "usda_pdp" and table == "samples":
            country_by_origin[(token(row["origin"]), token(row["country_missing_reason"]))] += 1
        if source == "usda_pdp" and table == "results":
            code = token(row["mean"])
            code_commodity[(token(row["commod"]), code)] += 1
            code_unit[(token(row["conunit"]), code)] += 1
            code_concen[(code, "null" if row["concen"] is None else "numeric")] += 1
            annotations[(code, token(row["annotate"]))] += 1
            sample_assays[row["sample_pk"]] += 1
            if code in {"O", "R"}:
                detection_groups[(row["sample_pk"], row["pestcode"])][code] += 1
                if row["concen"] is not None and row["lod"] is not None:
                    date_order["detected_concentration_below_lod"] += row["concen"] < row["lod"]
        if source == "noaa_ghcn_daily":
            key = (row["station_id"], row["element"], row["unit"])
            d = weather.setdefault(key, {"first_date": row["observation_date"], "last_date": row["observation_date"],
                                       "represented_slots": 0, "statuses": Counter(),
                                       "measurement_flags": Counter(), "quality_flags": Counter(), "source_flags": Counter()})
            d["first_date"] = min(d["first_date"], row["observation_date"])
            d["last_date"] = max(d["last_date"], row["observation_date"])
            d["represented_slots"] += 1
            d["statuses"][row["observation_status"]] += 1
            for flag in ("measurement", "quality", "source"):
                d[flag + "_flags"][token(row[flag + "_flag"])] += 1
            weather_year.setdefault((*key, row["observation_date"].year), Counter())[row["observation_status"]] += 1
        if source == "openfda_enforcement":
            for earlier, later in (("recall_initiation_date", "report_date"), ("recall_initiation_date", "termination_date"),
                                   ("center_classification_date", "report_date")):
                if row[earlier] is not None and row[later] is not None:
                    key = later + "_before_" + earlier
                    date_order[key + "__comparable"] += 1
                    if row[later] < row[earlier]:
                        date_order[key] += 1
                        if len(date_examples) < 10:
                            date_examples.append({"recall_number": row["recall_number"], "check": key,
                                                  "earlier": str(row[earlier]), "later": str(row[later])})
            date_order["empty_openfda_object"] += row["openfda"] == {}
    category_out = {}
    for name, counts in categories.items():
        category_out[name] = {"distinct_nonnull": None if name in overflow else len(counts),
                              "distinct_lower_bound": CAP + 1 if name in overflow else len(counts),
                              "status": "cap exceeded; top values withheld" if name in overflow else "exact",
                              "top": [] if name in overflow else ranked(counts),
                              "all_counts": dict(sorted(counts.items())) if name not in overflow and len(counts) <= 1000 else None}
    if table == "results" and source == "usda_pdp":
        special = {"mean_code_definitions": MEANINGS,
                   "commodity_by_mean": [{"commodity_code": a, "mean_code": b, "analytical_rows": v} for (a,b),v in sorted(code_commodity.items())],
                   "unit_by_mean": [{"unit_code": a, "mean_code": b, "analytical_rows": v} for (a,b),v in sorted(code_unit.items())],
                   "mean_by_concentration_presence": [{"mean_code": a, "concentration": b, "analytical_rows": v} for (a,b),v in sorted(code_concen.items())],
                   "mean_by_annotation": [{"mean_code": a, "annotation": b, "analytical_rows": v} for (a,b),v in sorted(annotations.items())],
                   "assays_per_represented_sample": summarize_counts(sample_assays),
                   "detected_sample_analyte_groups": len(detection_groups),
                   "detected_groups_with_both_original_and_reextraction": sum(bool(c["O"] and c["R"]) for c in detection_groups.values()),
                   "detected_groups_with_multiple_records": sum(sum(c.values()) > 1 for c in detection_groups.values()),
                   "detected_concentration_below_lod": date_order["detected_concentration_below_lod"],
                   "denominator_warning": "Analytical result rows, not independent food samples or regulatory exceedance prevalence"}
    elif source == "usda_pdp":
        special["origin_by_country_missing_reason"] = [{"origin_code": a, "missing_reason": b, "sample_rows": v} for (a,b),v in sorted(country_by_origin.items())]
    elif source == "noaa_ghcn_daily":
        series = []
        for (station, element, unit), d in sorted(weather.items()):
            span = (d["last_date"] - d["first_date"]).days + 1
            series.append({"station_id": station, "element": element, "unit": unit,
                           **d, "first_date": str(d["first_date"]), "last_date": str(d["last_date"]),
                           "calendar_days_in_inclusive_span": span,
                           "absent_calendar_slots_in_span": span - d["represented_slots"]})
        special = {"series": series, "yearly_status_counts": [
            {"station_id": k[0], "element": k[1], "unit": k[2], "year": k[3], "statuses": dict(v)}
            for k,v in sorted(weather_year.items())]}
    elif source == "openfda_enforcement":
        events = categories.get("event_id", Counter())
        special = {"date_order_audit": dict(date_order), "date_order_examples": date_examples,
                   "event_id_profile": summarize_counts(events) if "event_id" not in overflow else {"status": "cap exceeded"},
                   "recall_number_is_record_key": True}
    return {"rows": n, "row_granularity": schema["row_granularity"], "column_count": len(columns),
            "null_counts": {k: nulls[k] for k in columns}, "empty_string_counts": dict(empty),
            "literal_ambiguous_missing_tokens": dict(markers),
            "categories": category_out, "dates": dates,
            "numeric": {k: v.finish() for k,v in sorted(numeric.items())}, "investigation": special}


def summarize_counts(counts: Counter) -> dict:
    distribution = Numeric()
    for count in counts.values():
        distribution.add(count)
    return {"distinct_keys": len(counts), "rows": sum(counts.values()),
            "keys_with_multiple_records": sum(v > 1 for v in counts.values()),
            "records_beyond_first_per_key": sum(v - 1 for v in counts.values()),
            "records_per_key": distribution.finish()}


def inspect_rejections(path: Path) -> dict:
    """Inspect evidence within one source table; never resolve publisher conflicts."""
    reasons, states, crops = Counter(), Counter(), Counter()
    groups: dict[str, list[dict]] = defaultdict(list)
    rows = 0
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            evidence = json.loads(line)
            rows += 1
            reasons.update(evidence["reason_codes"])
            raw = evidence["raw_values"]
            if isinstance(raw, dict):
                states[token(raw.get("state"))] += 1
                crops[token(raw.get("crop_type"))] += 1
                if "conflicting_aggregate_key_all_versions_quarantined" in evidence["reason_codes"]:
                    groups[evidence["row_identifier"]].append(evidence)
    zero_nonzero = 0
    examples = []
    conflict_states, conflict_crops = Counter(), Counter()
    for key, versions in sorted(groups.items()):
        raw = versions[0]["raw_values"]
        metric = "production" if "production" in raw else "planted_area"
        values = {Decimal(v["raw_values"][metric]) for v in versions}
        zero_nonzero += Decimal(0) in values and any(v != 0 for v in values)
        conflict_states[token(raw.get("state"))] += 1
        conflict_crops[token(raw.get("crop_type"))] += 1
        if len(examples) < 12:
            examples.append({"row_identifier": key, "metric": metric,
                             "versions": [{"source_row_number": v["source_row_number"],
                                           "value": v["raw_values"][metric]} for v in versions]})
    return {"rejected_rows": rows, "reason_counts": dict(sorted(reasons.items())),
            "rejected_rows_by_state": dict(sorted(states.items())), "rejected_rows_by_crop_type": dict(sorted(crops.items())),
            "conflicting_key_groups": len(groups), "conflicting_groups_with_zero_and_nonzero": zero_nonzero,
            "conflicting_key_groups_by_state": dict(sorted(conflict_states.items())),
            "conflicting_key_groups_by_crop_type": dict(sorted(conflict_crops.items())), "conflict_examples": examples}


def inspect_issues(path: Path) -> dict:
    counts = Counter()
    examples = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            item = json.loads(line)
            counts[item["reason_code"]] += 1
            if len(examples) < 10:
                examples.append(item)
    return {"counts": dict(sorted(counts.items())), "examples": examples}


def inspect_openfda_presence(path: Path) -> dict:
    """Explain source field absence separately from explicit null/empty values."""
    records = json.loads(path.read_text(encoding="utf-8"))["results"]
    fields = sorted({k for row in records for k in row})
    return {"raw_rows": len(records), "fields": {
        field: dict(Counter("absent" if field not in row else
                            "null" if row[field] is None else
                            "empty_string" if row[field] == "" else
                            "empty_object" if row[field] == {} else "provided" for row in records))
        for field in fields},
        "warning": "Raw-source counts include the quarantined record; M2 accepted-row null counts use a different denominator."}


def noaa_flag_documentation(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    sections = {}
    for name, start, end in (("measurement", "MFLAG1     is", "QFLAG1     is"),
                             ("quality", "QFLAG1     is", "SFLAG1     is"),
                             ("source", "SFLAG1     is", "MFLAG2     is")):
        chunk = text.split(start, 1)[1].split(end, 1)[0]
        sections[name] = {code: description.strip() for code, description in
                          re.findall(r"^\s+(\S+)\s+=\s+([^\n]+)", chunk, re.MULTILINE)}
    return {"path": path.as_posix(), "sha256": sha256_file(path),
            "definitions_first_line_from_pinned_readme": sections,
            "warning": "Full definitions and continuation lines remain in the pinned README; flags are not reclassified."}


def verify_inputs(root: Path, summary: dict) -> dict:
    """Fail closed before profiling if the frozen upstream bytes/code changed."""
    for relative, digest in summary["cleaning_code_sha256"].items():
        if sha256_file(Path(__file__).parent / relative) != digest:
            raise ValueError("M2 producer code changed; revalidate upstream before M3")
    return verify_cleaned(root, summary)


def build_audit(root: Path) -> dict:
    summary_path = root / "reports/m2_cleaning_summary.json"
    summary = json.loads(summary_path.read_text())
    revalidation_path = root / "reports/m2_revalidation.json"
    revalidation = json.loads(revalidation_path.read_text())
    if summary["status"] != "COMPLETE" or revalidation["eligible_cohort_status"] != "COMPLETE":
        raise ValueError("M2 is not validated complete")
    if sha256_file(summary_path) != revalidation["summary"]["sha256"]:
        raise ValueError("M2 revalidation does not cover current summary")
    baseline = verify_inputs(root, summary)
    source_manifest = json.loads((root / summary["source_manifest"]).read_text())
    eligible = sorted(k for k,v in source_manifest["datasets"].items() if v.get("m2_eligible") is True)
    if eligible != sorted(summary["sources"]):
        raise ValueError("M2 cohort differs from M1 eligibility")
    directory = inside_root(root, summary["output_directory"])
    sources = {}
    for source_name, source in sorted(summary["sources"].items()):
        LOG.info("Profiling %s", source_name)
        result = {"intended_ml_role": source["intended_ml_role"], "tables": {},
                  "limitations": WARNINGS["opendosm" if source_name.startswith("opendosm_") else source_name]}
        for table, stats in sorted(source["tables"].items()):
            path = directory / source["output_subdirectory"] / (table + ".csv")
            schema = json.loads(path.with_suffix(".schema.json").read_text())
            profile = profile_table(read_table(path), schema, source_name, table)
            rejected = inspect_rejections(path.with_suffix(".rejected.jsonl"))
            if profile["rows"] != stats["clean_rows"] or rejected["rejected_rows"] != stats["rejected_rows"]:
                raise ValueError("M3 accounting differs from M2")
            if {k:v for k,v in profile["null_counts"].items() if v} != stats["missingness_after"]:
                raise ValueError("M3 null counts differ from M2")
            profile.update(m2_accounting={k:stats[k] for k in ("raw_rows", "clean_rows", "rejected_rows", "duplicate_rows")},
                           input_path=path.relative_to(root).as_posix(), rejections=rejected,
                           issues=inspect_issues(path.with_suffix(".issues.jsonl")))
            if source_name.startswith("opendosm_") and rejected["conflicting_key_groups"] != source.get("conflicting_key_groups", 0):
                raise ValueError("M3 conflict grouping differs from M2")
            result["tables"][table] = profile
        captured = {a["artifact_id"]: a for a in source_manifest["datasets"][source_name]["artifacts"] if a["status"] == "captured"}
        if source_name == "openfda_enforcement":
            result["raw_field_presence"] = inspect_openfda_presence(inside_root(root, captured["openfda_local_json"]["path"]))
        if source_name == "noaa_ghcn_daily":
            result["flag_documentation"] = noaa_flag_documentation(inside_root(root, captured["ghcn_readme"]["path"]))
            result["flag_documentation"]["path"] = captured["ghcn_readme"]["path"]
        sources[source_name] = result
    # Check bytes again after the complete read, including every schema/ledger and raw artifact.
    if output_hashes(directory) != summary["outputs"]:
        raise ValueError("M2 files changed during M3 audit")
    _, after = verify_baseline(root, root / summary["source_manifest"])
    if after != baseline["raw_integrity"]:
        raise ValueError("Raw integrity changed during M3")
    return {"milestone": "M3", "status": "COMPLETE", "data_status": "NOT MODEL-READY",
            "inputs": {p.relative_to(root).as_posix(): sha256_file(p) for p in (
                summary_path, root / "reports/m2_cleaning_report.md", revalidation_path)},
            "audit_code_sha256": sha256_file(Path(__file__)), "m2_verification": baseline,
            "raw_integrity_after": after, "sources": sources,
            "methods": {"rows": "Complete streaming census; no row sampling",
                        "null": "Explicit M2 null only; empty strings, blank flags, {}, zero and literal N/A are separate",
                        "category_cap": CAP, "cap_behavior": "Exact counts until cap; then lower bound only, no biased prefix ranking",
                        "numeric": "Exact min/max/mean/zero/negative counts; exact nearest-rank quantiles and 10 equal-width bins unless distinct-value cap exceeded",
                        "cross_source_joins": False, "features_created": False, "labels_created": False,
                        "runtime_dependencies": [], "s390x_executed": False},
            "pending_sources": revalidation["pending_sources"]}


def bars(title: str, pairs: list[tuple[str, int]], denominator: int, question: str) -> str:
    maximum = max((n for _,n in pairs), default=1) or 1
    body = "".join(f"<tr><th>{escape(k)}</th><td><meter min='0' max='{maximum}' value='{v}'></meter></td>"
                   f"<td>{v:,}</td><td>{(100*v/denominator if denominator else 0):.2f}%</td></tr>" for k,v in pairs)
    return (f"<h3>{escape(title)}</h3><p>{escape(question)} Denominator: {denominator:,} records. "
            "Bars scale to the largest displayed count.</p><table><thead><tr><th>Category</th><th>Count bar</th>"
            f"<th>Count</th><th>% of denominator</th></tr></thead><tbody>{body}</tbody></table>")


def write_reports(audit: dict, directory: Path) -> None:
    lines = ["# M3 — Source-specific EDA and data-quality audit", "", "**COMPLETE for the validated M2 cohort. NOT MODEL-READY.**", "",
             "Full streaming census of seven source tables. No source joins, predictive features, new labels, imputation or training.", "",
             "Reproduce: `PYTHONPATH=src python -m tracefront_data.eda`.", "",
             "The JSON contains per-column null/empty/token counts, categorical cardinality, date coverage, unit-specific numeric distributions, assay/flag diagnostics and rejected-record evidence. The HTML contains focused count visuals and expandable diagnostics.", "",
             "## Methods and interpretation", "",
             "- Nulls follow the M2 typed schema. Empty strings, blank flags, empty JSON objects, legitimate zero and literal N/A are counted separately.",
             "- Categorical counts are exact up to 10,000 distinct values per field. Above that, report a lower bound and withhold rankings. Free text is not treated as a useful category distribution.",
             "- Numeric quantiles use exact nearest rank; histogram bins are left-closed/right-open except the final inclusive bin. Numeric summaries separate units and NOAA element/status. Reference years and lineage integers are excluded from numeric distributions.",
             "- All percentages are descriptive frequencies of captured records. They do not establish population risks or contamination prevalence.",
             "- Every M1 raw artifact and M2 output was verified before profiling; their bytes were checked again after profiling.", ""]
    html = ["<!doctype html><html lang='en'><meta charset='utf-8'><title>M3 source audit</title>",
            "<style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:1rem;color:#18252b}table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{text-align:left;padding:.4rem;border-bottom:1px solid #ccc}meter{width:200px}pre{white-space:pre-wrap;overflow-wrap:anywhere}section{border-top:2px solid #789;margin-top:2rem}summary{cursor:pointer}</style>",
            "<h1>M3 source-specific audit</h1><p><strong>NOT MODEL-READY.</strong> Full source-table census. No joins, new labels, features or training. Expand diagnostics for exact denominators and numeric distributions.</p>"]
    for source_name, source in audit["sources"].items():
        lines += ["## " + source_name, "", "Role: " + source["intended_ml_role"], ""]
        html.append("<section><h2>" + escape(source_name) + "</h2>")
        for table, p in source["tables"].items():
            lines += ["### " + table, "", f"Rows: {p['rows']:,}. Grain: {p['row_granularity']}.", "",
                      "| Field with nulls | Count | % of clean rows |", "| --- | ---: | ---: |"]
            missing = sorted(((k,v) for k,v in p["null_counts"].items() if v), key=lambda x:(-x[1], x[0]))
            lines += [f"| {k} | {v:,} | {100*v/p['rows']:.2f}% |" for k,v in missing]
            if not missing:
                lines += ["| None | 0 | 0.00% |"]
            html.append(bars(table + " — nulls", missing[:10], p["rows"], "Which fields lack values, and how often?"))
            lines += ["", "Date coverage: `" + json.dumps({k:{"min":v["min"], "max":v["max"]} for k,v in p["dates"].items()}, sort_keys=True) + "`.", "",
                      "| Numeric field / unit partition | Nonnull | Zero | Min | Median | p95 | Max |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
            for name, distribution in p["numeric"].items():
                q = distribution["quantiles"] or {}
                lines.append(f"| {name} | {distribution['count']:,} | {distribution['zero_count']:,} | {distribution['min']} | {q.get('p50', 'unavailable')} | {q.get('p95', 'unavailable')} | {distribution['max']} |")
                if distribution["histogram"]:
                    pairs = [(f"[{b['lower']}, {b['upper']}{']' if b['upper_inclusive'] else ')'}", b["count"]) for b in distribution["histogram"]]
                    html.append(bars(table + " — " + name, pairs, distribution["count"], "How are observed numeric values distributed within this unit/status partition? Null values are excluded."))
            inv = p["investigation"]
            if source_name == "usda_pdp" and table == "results":
                codes = p["categories"]["mean"]["all_counts"]
                lines += ["", "MEAN result codes: `" + json.dumps(codes, sort_keys=True) + "`.", "",
                          f"Detected sample/analyte groups with both O and R: {inv['detected_groups_with_both_original_and_reextraction']:,}. These are repeated analytical evidence, not independent samples.", "",
                          "### Analytical-record codes by commodity", "", "| Commodity code | ND | NP | O | R | Analytical rows |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
                by_commodity = defaultdict(Counter)
                for row in inv["commodity_by_mean"]:
                    by_commodity[row["commodity_code"]][row["mean_code"]] = row["analytical_rows"]
                for commodity, counts in sorted(by_commodity.items()):
                    lines.append(f"| {commodity} | {counts['ND']:,} | {counts['NP']:,} | {counts['O']:,} | {counts['R']:,} | {sum(counts.values()):,} |")
                lines += ["", "Denominator: analytical records within each commodity code, not food-batch contamination frequency. Codes retain official source spelling; no product matching or source join."]
                html.append(bars("PDP result codes", sorted(codes.items()), p["rows"], "How does observed analytical evidence divide between ND, NP, original and re-extraction detections?"))
            elif source_name == "noaa_ghcn_daily":
                for series in inv["series"]:
                    lines += ["", f"- {series['station_id']} / {series['element']} ({series['unit']}): {series['first_date']} to {series['last_date']}; {series['represented_slots']:,} represented slots; {series['absent_calendar_slots_in_span']:,} absent calendar slots within that span.",
                              "- Status counts: `" + json.dumps(series["statuses"], sort_keys=True) + "`; quality flags: `" + json.dumps(series["quality_flags"], sort_keys=True) + "`."]
                    html.append(bars("NOAA " + series["element"] + " statuses", sorted(series["statuses"].items()), series["represented_slots"], "How many represented day/element records are missing or flagged? Entire absent calendar slots are excluded from this denominator."))
            elif source_name == "openfda_enforcement":
                lines += ["", "Date-order audit (comparable-pair denominators included): `" + json.dumps(inv["date_order_audit"], sort_keys=True) + "`.",
                          "", "Repeated event identifiers: `" + json.dumps(inv["event_id_profile"], sort_keys=True) + "`."]
                html.append(bars("Recall classification — contextual only", [(x["value"],x["count"]) for x in p["categories"]["classification"]["top"]], p["rows"], "What is the captured recall-classification mix? This is not contamination class balance."))
            rejected = p["rejections"]
            if rejected["rejected_rows"]:
                lines += ["", f"Rejections: {rejected['rejected_rows']:,}; reasons: `" + json.dumps(rejected["reason_counts"], sort_keys=True) + "`."]
            if p["issues"]["counts"]:
                lines += ["", "Retained issue counts: `" + json.dumps(p["issues"]["counts"], sort_keys=True) + "`."]
            if source_name.startswith("opendosm_"):
                coverage = p["dates"]["reference_date"]
                lines += ["", f"Annual reference coverage: {coverage['min']} to {coverage['max']}; not publication dates.",
                          f"Conflicting key groups: {rejected['conflicting_key_groups']:,}; groups containing both zero and nonzero values: {rejected['conflicting_groups_with_zero_and_nonzero']:,}."]
                if rejected["conflicting_key_groups"]:
                    html.append(bars("Conflicting keys by state", sorted(rejected["conflicting_key_groups_by_state"].items()), rejected["conflicting_key_groups"], "Where are quarantined conflicting aggregates concentrated? Each key is counted once."))
                    lines += ["", "Example conflicting keys (all versions remain quarantined):", ""]
                    lines += ["- `" + e["row_identifier"] + "`: " + ", ".join(v["value"] for v in e["versions"]) for e in rejected["conflict_examples"][:5]]
            html.append("<details><summary>" + escape(table) + " — complete profile and diagnostics</summary><pre>" + escape(json.dumps(p, indent=2, sort_keys=True)) + "</pre></details>")
        lines += ["", "Interpretation and leakage candidates:", ""] + ["- " + w for w in source["limitations"]] + [""]
        if "raw_field_presence" in source:
            lines += ["Raw-source field presence (includes the rejected record; absent fields explain null counts not shown in M2 lexical-blank counts):", "",
                      "```json", json.dumps(source["raw_field_presence"], indent=2, sort_keys=True), "```", ""]
            html.append("<details><summary>Raw-source field presence</summary><pre>" + escape(json.dumps(source["raw_field_presence"], indent=2, sort_keys=True)) + "</pre></details>")
        if "flag_documentation" in source:
            lines += ["Pinned NOAA flag definitions are included in the JSON, with the complete README path/checksum. Observed QFLAG D = failed duplicate check; K = failed streak/frequent-value check; O = failed climatological outlier check.", ""]
        html.append("<ul>" + "".join("<li>" + escape(w) + "</li>" for w in source["limitations"]) + "</ul></section>")
    lines += ["## Decisions and remaining issues", "",
              "- M3 eligible-source profiling is complete. No sample-level contamination prevalence or regulatory exceedance target was created.",
              "- PDP target definition must address censoring, assay panels, repeated extractions and effective regulatory thresholds separately. Result codes, concentration and annotations require outcome/predictor separation in later milestones.",
              "- NOAA coverage is station/element-specific; missing spans, QA flags and source changes require an explicit future policy before enrichment.",
              "- OpenDOSM conflicts require publisher clarification. Keep rejected versions; never select zero/nonzero or add them together by assumption.",
              "- openFDA snapshot provenance and historical field-availability gaps remain; recall frequencies cannot estimate incidence.",
              "- FSIS remains **official source confirmed, raw file not yet acquired**. FDA inspections remain pending. Neither was profiled.",
              "- Person B may inspect these descriptive reports. Source tables remain NOT MODEL-READY; canonical contracts, feature engineering, enrichment and formal leakage validation remain future work.",
              "- Python 3.11+ standard library only; no native dependency added. LinuxONE/s390x execution remains untested.", ""]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "m3_eda_summary.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (directory / "m3_eda_report.md").write_text("\n".join(lines), encoding="utf-8")
    (directory / "m3_eda_visuals.html").write_text("\n".join(html) + "</html>\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    root = Path.cwd()
    audit = build_audit(root)
    write_reports(audit, root / "reports")
    LOG.info("M3 audit complete: %s independent sources; NOT MODEL-READY", len(audit["sources"]))


if __name__ == "__main__":
    main()
