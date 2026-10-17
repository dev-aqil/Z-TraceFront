"""M5 evidence assessment, not a feature builder. Python standard library only.

Run: PYTHONPATH=src python -m tracefront_data.feature_readiness
Writes reports only; no source reads for transformation, joins, labels or models.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from tracefront_data.audit import sha256_file
from tracefront_data.contracts import load_verified_inputs, validate_contract
from tracefront_data.provenance import inside_root

USES = {"INPUT", "GROUP_KEY", "PRIOR_OUTCOME", "REFERENCE_TIME", "QUALITY"}


def unit_readiness(field: dict, table: dict) -> str:
    """A coded unit is usable evidence only with a verified in-table mapping."""
    if field["datatype"] not in {"decimal", "integer"}:
        return "NOT_APPLICABLE"
    unit = field["unit"]
    if unit["status"] == "VERIFIED" and unit["canonical"]:
        return "CONFIRMED"
    if unit["status"] == "SOURCE_CODED":
        names = {f["canonical_name"] for f in table["fields"].values()}
        if unit.get("unit_column") in names and (unit.get("code_meanings") or unit.get("element_units")):
            return "CONFIRMED_SOURCE_CODED"
    return "PENDING"


def verify_m5_evidence(root: Path, scope: dict) -> dict:
    """Fingerprint every cited M5 availability-evidence file; never trust an unverified claim."""
    checked = {}
    for ref, record in scope.get("m5_evidence", {}).items():
        path = inside_root(root, record["evidence_path"])
        if sha256_file(path) != record["evidence_sha256"]:
            raise ValueError("M5 evidence fingerprint changed: " + ref)
        checked[ref] = record["evidence_sha256"]
    return checked


def _m5_overlay(contract: dict, scope: dict) -> tuple[dict, dict]:
    """Load M5-specific availability/predictor overrides without ever rewriting M4."""
    evidence = scope.get("m5_evidence", {})
    family_ids = {f["id"] for f in scope["families"]}
    for fid in scope["decision_contract"].get("applies_to_families", []):
        if fid not in family_ids:
            raise ValueError("decision_contract.applies_to_families references an unknown family")
    tables: dict[str, dict] = {}
    for entry in scope.get("m5_verified_tables", []):
        if entry["evidence_ref"] not in evidence:
            raise ValueError("Unknown M5 evidence reference: " + entry["evidence_ref"])
        if entry["table"] not in contract["tables"]:
            raise ValueError("M5 table override references an unknown source table")
        tables[entry["table"]] = entry
    inputs: dict[tuple[str, str], dict] = {}
    for entry in scope.get("m5_verified_inputs", []):
        if entry["evidence_ref"] not in evidence:
            raise ValueError("Unknown M5 evidence reference: " + entry["evidence_ref"])
        if entry["table"] not in contract["tables"] or entry["column"] not in contract["tables"][entry["table"]]["fields"]:
            raise ValueError("M5 input override references an unknown source field")
        inputs[(entry["table"], entry["column"])] = entry
    return tables, inputs


def assess_families(contract: dict, scope: dict) -> dict:
    """Report prerequisites from pinned metadata; never promote field approval.

    M5 availability/predictor evidence is additive and table/field-scoped: it can clear
    PREDICTION_TIME_AVAILABILITY_UNVERIFIED / PREDICTOR_APPROVAL_PENDING only for the exact
    (table, column) pairs it cites, with a real dated source and only up to the documented
    prediction_cutoff. It never edits the frozen M4 contract. The decision_contract itself
    (experiment definition, cutoff, blanket availability_evidence) only applies to the
    families explicitly listed in decision_contract.applies_to_families; every other family
    is assessed exactly as if no experiment had been chosen.
    """
    if any(scope.get(k) is not False for k in ("materialize_features", "joins_authorized", "labels_authorized")):
        raise ValueError("M5 assessment cannot authorize materialization, joins or labels")
    definitions = scope["unmet_requirement_definitions"]
    ids = set()
    families = []
    decision = scope["decision_contract"]
    cutoff = decision.get("prediction_cutoff")
    in_scope = set(decision.get("applies_to_families", []))
    verified_tables, verified_inputs = _m5_overlay(contract, scope)
    for family in scope["families"]:
        if family["id"] in ids:
            raise ValueError("Duplicate family ID")
        ids.add(family["id"])
        reasons, fields = set(), []
        covered = family["id"] in in_scope
        if not decision["experiment_definition"] or not covered:
            reasons.add("EXPERIMENT_DEFINITION_PENDING")
        if not decision["prediction_cutoff"] or not decision["prediction_cutoff_precision"] or not covered:
            reasons.add("PREDICTION_CUTOFF_UNDEFINED")
        if not decision["availability_evidence"] or not covered:
            reasons.add("PREDICTION_TIME_AVAILABILITY_UNVERIFIED")
        if not family["references"]:
            reasons.add("NO_ELIGIBLE_SOURCE_INPUTS")
        for requirement in family["unmet_requirements"]:
            if requirement not in definitions:
                raise ValueError("Unknown unmet prerequisite: " + requirement)
            reasons.add(requirement)
        for pending in family["pending_sources"]:
            if pending not in contract["pending_sources"]:
                raise ValueError("Unknown pending source")
            if contract["pending_sources"][pending]["mappings"]:
                raise ValueError("Pending source changed; reassess the pinned cohort")
            reasons.add("SOURCE_NOT_ACQUIRED")
        for ref in family["references"]:
            if ref["use"] not in USES:
                raise ValueError("Unknown reference use")
            if ref["table"] not in contract["tables"]:
                raise ValueError("Unknown source table; no fabricated source fields permitted")
            table = contract["tables"][ref["table"]]
            if ref["column"] not in table["fields"]:
                raise ValueError("Unknown source column; no fabricated source fields permitted")
            field = table["fields"][ref["column"]]
            table_m5 = verified_tables.get(ref["table"])
            field_m5 = verified_inputs.get((ref["table"], ref["column"]))
            table_available = table["history_availability"]["status"] == "VERIFIED" or (
                covered and table_m5 is not None and cutoff is not None and table_m5["available_at"] <= cutoff)
            field_available = field["prediction_time_availability"]["status"] == "VERIFIED" or (
                covered and field_m5 is not None and cutoff is not None and field_m5["available_at"] <= cutoff)
            if not table_available or not field_available:
                reasons.add("PREDICTION_TIME_AVAILABILITY_UNVERIFIED")
            unit_status = unit_readiness(field, table) if ref["use"] == "INPUT" else "NOT_APPLICABLE"
            m5_predictor_ok = covered and field_m5 is not None and table_available and field_available
            if ref["use"] == "INPUT":
                predictor_ok = (field["predictor_approved"] or m5_predictor_ok) and (
                    field["canonical_name"] in table["predictor_allowlist"] or m5_predictor_ok)
                if not predictor_ok:
                    reasons.add("PREDICTOR_APPROVAL_PENDING")
                if field["role"] in {"OUTCOME_EVIDENCE", "RETROSPECTIVE_CONTEXT"}:
                    reasons.add("FOCAL_OUTCOME_INPUT_EXCLUDED")
                if field["role"] in {"IDENTIFIER", "LINEAGE"}:
                    reasons.add("IDENTIFIER_NOT_APPROVED_AS_PREDICTOR")
                if unit_status == "PENDING":
                    reasons.add("UNIT_VERIFICATION_PENDING")
            fields.append({**ref, "canonical_name": field["canonical_name"], "role": field["role"],
                           "unit_readiness": unit_status, "source_unit_status": field["unit"]["status"],
                           "field_availability": "M5_VERIFIED" if (field_available and field["prediction_time_availability"]["status"] != "VERIFIED") else field["prediction_time_availability"]["status"],
                           "historical_availability": "M5_VERIFIED" if (table_available and table["history_availability"]["status"] != "VERIFIED") else table["history_availability"]["status"],
                           "predictor_approved": field["predictor_approved"] or m5_predictor_ok, "leakage_class": field["leakage_class"]})
        # No configuration field can claim READY or turn this assessor into an executor;
        # REQUIRES_IMPLEMENTATION_REVIEW still requires a separate, explicit materialization run.
        families.append({"id": family["id"], "purpose": family["purpose"], "scope": family["scope"],
                         "status": "BLOCKED" if reasons else "REQUIRES_IMPLEMENTATION_REVIEW",
                         "reason_codes": sorted(reasons), "field_assessments": fields,
                         "pending_sources": family["pending_sources"], "features_emitted": 0})
    excluded = [{"table": key, "column": column, "canonical_name": field["canonical_name"],
                 "role": field["role"], "leakage_class": field["leakage_class"],
                 "reason": "Excluded as a direct focal predictor; no new outcome or target derived. Prior-outcome use still requires event/availability/entity/comparability evidence."}
                for key, table in sorted(contract["tables"].items()) for column, field in table["fields"].items()
                if field["role"] in {"OUTCOME_EVIDENCE", "RETROSPECTIVE_CONTEXT"}]
    cleared = sorted(f["id"] for f in families if f["status"] != "BLOCKED")
    implementation_status = (
        "No feature family implemented; prerequisites remain unresolved" if not cleared else
        f"{len(cleared)} family(ies) cleared evidence review for implementation ({', '.join(cleared)}); "
        "materialization happens in a separate module (pdp_sample_context_features), not this assessor. "
        "All other families remain unresolved.")
    return {"milestone": "M5", "status": "PARTIAL", "assessment_status": "COMPLETE",
            "implementation_status": implementation_status,
            "data_status": "NOT MODEL-READY", "family_status_counts": dict(Counter(f["status"] for f in families)),
            "families": families, "excluded_direct_focal_inputs": excluded,
            "features_emitted": 0, "feature_tables_written": 0, "labels_created": 0, "joins_performed": 0,
            "decision_contract": decision, "unmet_requirement_definitions": definitions,
            "pending_sources": contract["pending_sources"]}


def verify_m4(root: Path) -> tuple[dict, dict]:
    record_path = root / "reports/m4_validation.json"
    record = json.loads(record_path.read_text())
    if record["status"] != "COMPLETE":
        raise ValueError("M4 validation is not complete")
    pins = {"reports/m4_validation.json": sha256_file(record_path)}
    for relative, metadata in record["artifacts"].items():
        path = inside_root(root, relative)
        if path.stat().st_size != metadata["size_bytes"] or sha256_file(path) != metadata["sha256"]:
            raise ValueError("M4 artifact changed: " + relative)
        pins[relative] = metadata["sha256"]
    for relative, digest in record["code_sha256"].items():
        if sha256_file(inside_root(root, relative)) != digest:
            raise ValueError("M4 producer/test fingerprint changed")
        pins[relative] = digest
    schemas, profiles, _, upstream = load_verified_inputs(root)
    contract = json.loads((root / "configs/source_contracts.json").read_text())
    checks = validate_contract(contract, schemas, profiles)
    if checks != record["contract_checks"]:
        raise ValueError("M4 metadata checks changed")
    return contract, {"m4_input_sha256": pins, "m4_checks": checks, "upstream": upstream}


def render_report(summary: dict) -> str:
    cleared = sorted(f["id"] for f in summary["families"] if f["status"] != "BLOCKED")
    header = ("**Milestone PARTIAL. Assessment COMPLETE. Feature implementation remains blocked. NOT MODEL-READY.**" if not cleared else
              f"**Milestone PARTIAL. Assessment COMPLETE. {len(cleared)} family(ies) cleared review for implementation; the remaining families stay blocked. NOT MODEL-READY (no joins/labels/training have occurred).**")
    intro = ("No acquired family currently has all of the required inputs, units, prediction-cutoff definition, availability evidence and predictor review. No row-level feature calculations, final labels, source joins or models were implemented." if not cleared else
             f"{', '.join(cleared)} now have a documented experiment, prediction cutoff and field-specific official availability evidence; their implementation (if any) is produced by a separate materialization module, not this assessor. Every other family still lacks required inputs, units, cutoff definition, availability evidence or predictor review. No cross-source join, final label or model was implemented anywhere in M5.")
    lines = ["# M5 — Feature feasibility and readiness", "", header, "",
             intro, "",
             "## Family assessment", "", "| Family | Status | Unresolved requirements |", "| --- | --- | --- |"]
    for family in summary["families"]:
        lines.append("| " + family["id"] + " | " + family["status"] + " | " + ", ".join(family["reason_codes"]) + " |")
    for family in summary["families"]:
        lines += ["", "## " + family["id"], "", family["purpose"], "", family["scope"], "",
                  "| Source table / existing M2 field | Intended use | Units | Field / historical availability |", "| --- | --- | --- | --- |"]
        for field in family["field_assessments"]:
            lines.append(f"| {field['table']} / {field['column']} | {field['use']} | {field['unit_readiness']} | {field['field_availability']} / {field['historical_availability']} |")
        if not family["field_assessments"]:
            lines += ["| No defensible acquired source inputs | none | not assessed | pending |"]
        lines += ["", "Unmet source/policy prerequisites:", ""]
        for reason in family["reason_codes"]:
            lines.append("- `" + reason + "`: " + summary["unmet_requirement_definitions"].get(reason, {
                "EXPERIMENT_DEFINITION_PENDING": "No source-specific deployment experiment has been selected; no new target is defined by this assessment.",
                "PREDICTION_CUTOFF_UNDEFINED": "No documented deployment decision point or precision; do not invent T to unblock features.",
                "PREDICTION_TIME_AVAILABILITY_UNVERIFIED": "M4 availability remains pending. Sample/reference/report dates and today's retrieval clock do not establish historical as-of values.",
                "PREDICTOR_APPROVAL_PENDING": "The referenced base inputs are not on an approved source-specific predictor list.",
                "UNIT_VERIFICATION_PENDING": "No confirmed canonical physical unit; retain publisher declarations without converting.",
                "NO_ELIGIBLE_SOURCE_INPUTS": "Required observations are absent from acquired M4 source tables.",
                "SOURCE_NOT_ACQUIRED": "Required official source remains pending, with no invented mapping.",
                "FOCAL_OUTCOME_INPUT_EXCLUDED": "Analytical evidence/retrospective fields cannot be used as direct focal predictors.",
                "IDENTIFIER_NOT_APPROVED_AS_PREDICTOR": "Lineage and grouping identifiers are not approved predictors."
            }.get(reason, "Requires explicit evidence and review.")))
    lines += ["", "## Direct focal-input exclusions", "",
              f"{len(summary['excluded_direct_focal_inputs'])} existing outcome/retrospective fields are excluded as direct focal inputs; these are evidence roles, not new labels.", "",
              "| Source table | M2 field | Canonical declaration | Role / leakage |", "| --- | --- | --- | --- |"]
    for field in summary["excluded_direct_focal_inputs"]:
        lines.append(f"| {field['table']} | {field['column']} | {field['canonical_name']} | {field['role']} / {field['leakage_class']} |")
    lines += ["", "## Scientific boundaries and next evidence", "",
              "- PDP product/sample fields may eventually support a chemical experiment. Collection is not digital/result availability, sample unit count is not batch mass, and sample-ID suffix/lab/site codes are not supplier/factory entities. Existing year/month/day fields and M2 missingness reasons were not repackaged as new M5 features.",
              "- Prior outcomes can inform history only after strict event AND result/public-availability filtering, verified identities, a tested denominator/comparability definition and focal-sample exclusion. No history feature or final contamination target was created here.",
              "- NOAA's mm/degC mappings are confirmed within element. That does not resolve day boundaries, QA/coverage policy or the timing of public availability. Weather is not a batch-linked cold-chain sensor. No rainfall/temperature window, threshold or missing-day imputation was computed.",
              "- OpenDOSM area units are hectares, but reference year is not release time. Production units remain pending. District conflicts remain quarantined; overlapping state/national totals were not summed.",
              "- Recall status, classification, reason and termination reflect retrospective snapshots. They cannot be backfilled to report/initiation dates. Firm strings do not establish supplier identity, and current recall objects are not safe/contaminated labels.",
              "- Cold-chain and supply-chain timing require actual batch-linked sensor/stage/expiry records. Product-specific safety thresholds cannot be inferred from regional weather or adopted universally.",
              "- FSIS remains **official source confirmed, raw file not yet acquired**. FDA inspections remain pending. No pending source was acquired or fabricated in M5.", "",
              "## What was implemented and verified", "",
              ("Only an evidence-based readiness assessment, source/policy scope file, regression tests and these reports. This assessor has no feature/materialization executor itself. No numerical feature helper was added for an unsupported family. All M1–M4 inputs are checked against their pinned evidence before assessment." if not cleared else
               "An evidence-based readiness assessment plus, for the cleared families only, a separate `tracefront_data.pdp_sample_context_features` module that re-checks this same assessment before reading the single pinned `usda_pdp.samples` M2 table (no `usda_pdp.results`, no joins) and writing a source-specific, un-joined, unlabeled feature table under `data/interim/m5_v1/`. See `reports/m5_pdp_sample_context_features_report.md` for exactly what it wrote. This assessor itself still performs no materialization. All M1–M4 inputs are checked against their pinned evidence before assessment."), "",
              "Reproduce: `PYTHONPATH=src python -m tracefront_data.feature_readiness`. Output is limited to `reports/m5_feature_readiness.json` and `reports/m5_feature_report.md`. Completed assessment exits zero; inspect milestone/status counts to distinguish execution success from feature readiness.", "",
              "Python 3.11+ standard library only. No dependency or native compilation introduced. Existing M2 verification helpers require the same Python SQLite support already documented. LinuxONE/s390x execution remains untested.", "",
              "Person B may inspect the assessment, not use it as a model-ready feature matrix. Empty allowlists and pending availability are unchanged except where this report states otherwise. This is not the final M7 leakage audit and no training claim follows from the checks.", "",
              "## Remaining M5 work", "",
              ("Choose a real source-specific experiment and decision cutoff (with precision); obtain field-version/result availability evidence, resolve units and entity semantics, and document source-specific quality/window policies before any field is promoted. This requires real evidence, not changing a pending flag or treating acquisition time as historical publication." if not cleared else
               f"{', '.join(cleared)} are implemented at the M5 source-specific layer only; cross-source enrichment, leakage audit and any label/target remain future milestones. `pdp_input_missingness` stays pending `MISSINGNESS_SEMANTICS_POLICY_UNDEFINED`. The other eight families are unchanged from the prior assessment and still need their own named experiment, cutoff and evidence."), "",
              "Continue M5 after prerequisites are resolved; do not advance automatically to enrichment or modeling. A suitable next prompt is: 'Continue M5 for one named experiment. Supply the actual decision cutoff, input-availability evidence and applicable unit/quality policies. Reassess readiness and implement only the source-specific features that pass; keep other families pending. No source joins, invented labels or model training.'", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    root = Path.cwd()
    contract, evidence = verify_m4(root)
    scope_path = root / "configs/m5_feature_scope.json"
    scope = json.loads(scope_path.read_text())
    if scope["source_contract_sha256"] != sha256_file(root / "configs/source_contracts.json"):
        raise ValueError("M5 scope does not cover the pinned M4 contract")
    m5_evidence_sha256 = verify_m5_evidence(root, scope)
    summary = assess_families(contract, scope)
    summary.update(evidence=evidence, m5_evidence_sha256=m5_evidence_sha256, scope_sha256=sha256_file(scope_path),
                   assessor_sha256=sha256_file(Path(__file__)), runtime_dependencies_added=[], s390x_executed=False)
    # Fixed report paths only; no data/raw, interim, processed or model writes.
    (root / "reports/m5_feature_readiness.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "reports/m5_feature_report.md").write_text(render_report(summary), encoding="utf-8")
    print(json.dumps({"assessment_status": summary["assessment_status"], "milestone_status": summary["status"],
                      "families": summary["family_status_counts"], "features_emitted": 0}, indent=2))


if __name__ == "__main__":
    main()
