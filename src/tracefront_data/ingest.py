"""M1 source capture, manual FSIS intake and offline manifest verification.

Run: PYTHONPATH=src python -m tracefront_data.ingest --help
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import logging
from pathlib import Path
import platform
import sys
from typing import Any
from urllib.parse import urljoin, urlsplit
from uuid import uuid4
import zipfile

from tracefront_data.audit import audit_snapshot, sha256_file
from tracefront_data.fsis import inspect_fsis, json_pointer
from tracefront_data.provenance import (
    capture_artifact, inside_root, publish_stream, utc_now, verify_manifest, write_manifest,
)

LOGGER = logging.getLogger(__name__)


class ResourceLinks(HTMLParser):
    """Expose official links for review, without guessing a file or fiscal year."""

    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                url = urljoin(self.base_url, href)
                if urlsplit(url).scheme == "https":
                    self.links.append(url)


def captured_path(root: Path, artifacts: list[dict[str, Any]], artifact_id: str) -> Path | None:
    match = next((a for a in artifacts if a["artifact_id"] == artifact_id and a["status"] == "captured"), None)
    return inside_root(root, match["path"]) if match else None


def inspect_fsis_catalog(metadata: dict[str, Any], definition: dict[str, Any]) -> dict[str, Any]:
    """Confirm the official reference, without inferring a sample schema from DCAT."""
    if metadata.get("identifier") != definition["source_identifier"]:
        raise ValueError("catalog dataset identifier differs from configured source")
    if metadata.get("license") != definition["license_url"]:
        raise ValueError("catalog license declaration differs from configured source; review the new metadata")
    distributions = metadata.get("distribution", [])
    if not any(item.get("accessURL") == definition["resource_url"] for item in distributions):
        raise ValueError("official resource URL is not confirmed by the catalog distribution")
    descriptions = {key: metadata[key] for key in ("fields", "columns") if metadata.get(key)}
    references = []
    for item in [metadata, *distributions]:
        if item.get("describedBy"):
            references.append(item["describedBy"])
    return {
        **{key: metadata.get(key) for key in ("identifier", "modified", "issued", "license", "distribution")},
        "sample_field_descriptions": descriptions or None,
        "sample_schema_references": references,
        "data_dictionary_status": "official_metadata_evidence_requires_review" if descriptions or references else "pending_official_sample_file_or_documentation",
        "catalog_dates_are_sample_release_dates": False,
    }


def inspect_openfda(root: Path, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    local = captured_path(root, artifacts, "openfda_local_json")
    archive = captured_path(root, artifacts, "openfda_local_zip")
    if local is None:
        return {"status": "local_snapshot_missing_or_hash_mismatch", "training_eligible": False}
    audit = audit_snapshot(local, archive)
    upstream = captured_path(root, artifacts, "openfda_upstream_zip")
    index = captured_path(root, artifacts, "openfda_download_index")
    endpoint = None
    if index is not None:
        endpoint = json.loads(index.read_bytes())["results"]["food"]["enforcement"]
    archive_ok = archive is not None and audit["archive"]["crc_error_member"] is None and audit["archive"]["member_matches_input"]
    return {
        "status": "registered_context_only" if archive_ok else "archive_review_required",
        "rows": audit["rows"], "column_count": audit["column_count"],
        "json_sha256": audit["sha256"], "local_archive_matches_json": archive_ok,
        "official_archive_matches_local_archive": sha256_file(upstream) == sha256_file(archive) if upstream and archive else None,
        "official_download_metadata": endpoint,
        "embedded_source_metadata": audit["source_metadata_unverified"],
        "original_acquisition_time": None,
        "provenance_note": "A current byte match verifies this copy against today's official artifact; it does not recover its original retrieval time.",
        "training_eligible": False, "role": "context_only", "joined_to_fsis": False,
    }


def inspect_registered_fsis(root: Path, artifacts: list[dict[str, Any]], contract: dict[str, Any]) -> dict[str, Any]:
    data = captured_path(root, artifacts, "fsis_data")
    if data is None:
        return {
            "status": "awaiting_official_file", "training_eligible": False,
            "reason": "No official sample artifact registered. HTTP 403 is a session access restriction, not evidence of dataset unavailability.",
        }
    if contract.get("mapping_reviewed") and contract.get("reviewed_source_sha256") != sha256_file(data):
        raise ValueError("reviewed FSIS contract must pin this exact source artifact's SHA-256")
    profile = inspect_fsis(data, contract)
    dictionary = captured_path(root, artifacts, "fsis_matching_dictionary")
    dictionary_evidence: dict[str, Any] = {"separate_artifact_present": dictionary is not None}
    if data.suffix.lower() == ".json" and contract.get("dictionary_pointer") is not None:
        dictionary_value = json_pointer(json.loads(data.read_bytes()), contract["dictionary_pointer"])
        if not dictionary_value:
            raise ValueError("dictionary_pointer identifies empty documentation")
        dictionary_evidence["embedded_pointer"] = contract["dictionary_pointer"]
        dictionary_evidence["embedded_dictionary_present"] = True
    dictionary_ok = dictionary is not None or dictionary_evidence.get("embedded_dictionary_present", False)
    ready = profile["readiness"] == "cohort_inspected" and dictionary_ok and contract.get("dictionary_release_match_verified", False)
    return {
        "status": "cohort_inspected" if ready else "source_registered_review_pending",
        "profile": profile, "dictionary_evidence": dictionary_evidence,
        "manual_official_origin_note": "Manual origin/release is an operator assertion unless independently byte-verified; local hashes verify preservation, not publisher authenticity.",
        "training_eligible": False,
    }


def run_ingestion(
    root: Path, config_path: Path, contract_path: Path, *,
    fsis_file: str | None = None, fsis_data_url: str | None = None,
    fsis_dictionary: str | None = None, fsis_source_version: str | None = None,
    fsis_retrieved_at: str | None = None, fsis_origin_url: str | None = None,
    offline: bool = False,
) -> tuple[Path, dict[str, Any]]:
    root = root.resolve()
    config = json.loads(config_path.read_bytes())
    contract = json.loads(contract_path.read_bytes())
    if fsis_file and fsis_data_url:
        raise ValueError("choose manual FSIS intake or direct download, not both")
    if (fsis_file or fsis_data_url) and not fsis_source_version:
        raise ValueError("provide the official FSIS release/version; do not infer it from the catalog modified date")
    for url in (fsis_data_url, fsis_origin_url):
        if url is None:
            continue
        host = urlsplit(url).hostname or ""
        if urlsplit(url).scheme != "https" or (host != "fsis.usda.gov" and not host.endswith(".fsis.usda.gov")):
            raise ValueError("FSIS downloads must use an official FSIS host; unverified mirrors are not accepted")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]
    manifest: dict[str, Any] = {
        "manifest_version": 1, "run_id": run_id, "created_at": utc_now(),
        "milestone": "M1", "status": "partial", "source_config": config,
        "source_config_sha256": sha256_file(config_path),
        "pipeline_code_sha256": {path.name: sha256_file(path) for path in sorted(Path(__file__).parent.glob("*.py"))},
        "fsis_contract": contract, "fsis_contract_sha256": sha256_file(contract_path),
        "runtime": {"python": platform.python_version(), "architecture": platform.machine(), "system": platform.system()},
        "datasets": {},
    }
    for dataset_id, definition in config["datasets"].items():
        specs = [dict(item) for item in definition["artifacts"]]
        if dataset_id == "fsis_raw_poultry":
            if fsis_file or fsis_data_url:
                filename = Path(urlsplit(fsis_data_url).path if fsis_data_url else fsis_file).name
                spec = {"artifact_id": "fsis_data", "role": "official_biological_source_pending_inspection",
                        "filename": filename, "source_version": fsis_source_version,
                        "source_reference_url": definition["resource_url"]}
                if fsis_data_url:
                    spec["url"] = fsis_data_url
                else:
                    spec.update(local_path=fsis_file, retrieved_at=fsis_retrieved_at, declared_download_url=fsis_origin_url)
                specs.append(spec)
            if fsis_dictionary:
                specs.append({"artifact_id": "fsis_matching_dictionary", "role": "operator_supplied_matching_dictionary",
                              "filename": Path(fsis_dictionary).name, "local_path": fsis_dictionary,
                              "source_version": fsis_source_version, "source_reference_url": definition["resource_url"]})
        artifacts = []
        for spec in specs:
            LOGGER.info("Capturing %s", spec["artifact_id"])
            if offline and "url" in spec:
                record = {"artifact_id": spec["artifact_id"], "role": spec["role"], "source_url": spec["url"],
                          "status": "not_attempted", "reason": "offline mode", "retrieved_at": None}
            else:
                record = capture_artifact(spec, root, definition["directory"])
            artifacts.append(record)
        entry: dict[str, Any] = {
            "role": definition["intended_role"], "license": definition["license"],
            "license_url": definition["license_url"], "source_release_version": fsis_source_version if dataset_id == "fsis_raw_poultry" else definition["source_release_version"],
            "artifacts": artifacts,
        }
        try:
            if dataset_id == "openfda_enforcement":
                entry["inspection"] = inspect_openfda(root, artifacts)
            elif dataset_id == "fsis_raw_poultry":
                entry["source_status"] = "official source reference configured; catalog not verified in this run"
                entry["inspection"] = inspect_registered_fsis(root, artifacts, contract)
                catalog = captured_path(root, artifacts, "fsis_catalog_metadata")
                if catalog:
                    metadata = json.loads(catalog.read_bytes())
                    entry["catalog_evidence"] = inspect_fsis_catalog(metadata, definition)
                    entry["source_status"] = (
                        "official source confirmed, raw file acquired; inspection required"
                        if captured_path(root, artifacts, "fsis_data") is not None
                        else "official source confirmed, raw file not yet acquired"
                    )
                page = captured_path(root, artifacts, "fsis_resource_page")
                if page:
                    parser = ResourceLinks(definition["resource_url"])
                    parser.feed(page.read_text(encoding="utf-8"))
                    entry["resource_links_for_review"] = sorted(set(parser.links))
        except (OSError, ValueError, KeyError, TypeError) as error:
            entry["inspection"] = {"status": "inspection_failed", "error": str(error), "training_eligible": False}
        entry["acquisition_gaps"] = [a["artifact_id"] for a in artifacts if a["status"] != "captured"]
        manifest["datasets"][dataset_id] = entry
    fsis = manifest["datasets"].get("fsis_raw_poultry", {})
    fda = manifest["datasets"].get("openfda_enforcement", {})
    if fsis.get("inspection", {}).get("status") == "cohort_inspected" and fda.get("inspection", {}).get("status") == "registered_context_only":
        # Discovery/history-reference pages are optional once actual official data
        # and a matching dictionary have been registered and inspected.
        required = {"fsis_catalog_metadata", "fsis_data", "openfda_local_json", "openfda_local_zip", "openfda_license", "openfda_dictionary"}
        captured = {a["artifact_id"] for d in manifest["datasets"].values() for a in d["artifacts"] if a["status"] == "captured"}
        if required <= captured:
            manifest["status"] = "complete"
    manifest["integrity"] = verify_manifest(root, manifest)
    if not manifest["integrity"]["integrity_ok"]:
        manifest["status"] = "partial"
    path = write_manifest(root, manifest)
    return path, manifest


def restore_manifest(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Restore only missing captured artifacts with the recorded hashes pinned.

    Mutable upstream releases that changed fail instead of silently substituting
    a newer release. Original manifest and its timestamps are not rewritten.
    """
    root = root.resolve()
    results = []
    receipt_datasets: dict[str, Any] = {}
    for dataset_id, dataset in manifest["datasets"].items():
        artifacts = dataset["artifacts"]
        upstream_archive = next((a for a in artifacts if a["artifact_id"] == "openfda_upstream_zip" and a["status"] == "captured"), None)
        verified_openfda = dataset_id == "openfda_enforcement" and dataset.get("inspection", {}).get("official_archive_matches_local_archive") is True
        # Restore the verified official archive first; it also restores identical
        # local ZIP bytes and can reproduce a missing JSON without the tmp copy.
        ordered = sorted(artifacts, key=lambda a: a["artifact_id"] != "openfda_upstream_zip") if verified_openfda else artifacts
        for artifact in ordered:
            if artifact["status"] != "captured":
                continue
            path = inside_root(root, artifact["path"])
            if path.exists():
                if path.is_symlink() or sha256_file(path) != artifact["sha256"]:
                    raise ValueError("refusing to replace corrupt existing artifact; investigate it first")
                continue
            spec = {"artifact_id": artifact["artifact_id"], "role": artifact["role"], "filename": path.name,
                    "expected_sha256": artifact["sha256"], "max_bytes": max(artifact["size_bytes"], 1),
                    "source_version": artifact.get("source_version")}
            if artifact.get("source_url"):
                spec["url"] = artifact["source_url"]
            elif artifact.get("source_path") and inside_root(root, artifact["source_path"]).exists():
                spec.update(local_path=artifact["source_path"], retrieved_at=artifact.get("retrieved_at"))
            elif artifact.get("declared_download_url"):
                spec["url"] = artifact["declared_download_url"]
            directory = manifest["source_config"]["datasets"][dataset_id]["directory"]
            archive_replay = verified_openfda and upstream_archive and artifact["artifact_id"] == "openfda_local_json"
            if "url" not in spec and "local_path" not in spec and not archive_replay:
                result = {"artifact_id": artifact["artifact_id"], "role": artifact["role"], "status": "failed",
                          "attempted_at": utc_now(), "error": "No original local file or recorded direct download URL available"}
            elif "url" not in spec and "local_path" not in spec:
                archive_path = inside_root(root, upstream_archive["path"])
                result = {"artifact_id": artifact["artifact_id"], "role": artifact["role"],
                          "method": "verified_archive_member_replay", "retrieved_at": None,
                          "source_archive_path": upstream_archive["path"],
                          "source_archive_sha256": upstream_archive["sha256"], "source_archive_member": path.name}
                try:
                    if sha256_file(archive_path) != upstream_archive["sha256"]:
                        raise ValueError("archive hash differs from verified source")
                    with zipfile.ZipFile(archive_path) as zipped, zipped.open(path.name) as member:
                        result.update(publish_stream(member, root=root, directory=directory, filename=path.name,
                                      expected_sha256=artifact["sha256"], expected_size=artifact["size_bytes"],
                                      max_bytes=max(artifact["size_bytes"], 1)))
                    result.update(status="captured", imported_at=utc_now())
                except (OSError, ValueError, KeyError) as error:
                    result.update(status="failed", error=str(error))
            else:
                result = capture_artifact(spec, root, directory)
            results.append(result)
            receipt_datasets.setdefault(dataset_id, {"artifacts": []})["artifacts"].append(result)
    verification = verify_manifest(root, manifest)
    receipt_path = None
    if results:
        receipt = {
            "manifest_version": 1, "operation": "restore", "milestone": "M1",
            "run_id": "restore-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8],
            "created_at": utc_now(), "parent_run_id": manifest["run_id"],
            "source_config": manifest["source_config"], "datasets": receipt_datasets,
            "status": "complete" if verification["integrity_ok"] else "partial",
        }
        receipt_path = str(write_manifest(root, receipt))
    return {"restored_attempts": results, "verification": verification, "restoration_receipt": receipt_path}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Capture source bytes and write a new immutable manifest")
    run.add_argument("--config", type=Path, default=Path("configs/ingestion_sources.json"))
    run.add_argument("--fsis-contract", type=Path, default=Path("configs/fsis_pilot.json"))
    run.add_argument("--fsis-file", help="Officially downloaded JSON/CSV path relative to root")
    run.add_argument("--fsis-data-url", help="Verified direct JSON/CSV URL on an official FSIS host")
    run.add_argument("--fsis-dictionary", help="Matching downloaded dictionary path relative to root")
    run.add_argument("--fsis-source-version", help="Official release/FY/version identifier, not catalog modified date")
    run.add_argument("--fsis-retrieved-at", help="Original manual retrieval time with timezone, only if known")
    run.add_argument("--fsis-origin-url", help="Actual direct official URL used for a manual download, if known")
    run.add_argument("--offline", action="store_true")
    for name in ("verify", "restore"):
        command = sub.add_parser(name)
        command.add_argument("manifest", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if args.command == "run":
            path, manifest = run_ingestion(
                args.root, args.root / args.config, args.root / args.fsis_contract,
                fsis_file=args.fsis_file, fsis_data_url=args.fsis_data_url,
                fsis_dictionary=args.fsis_dictionary, fsis_source_version=args.fsis_source_version,
                fsis_retrieved_at=args.fsis_retrieved_at, fsis_origin_url=args.fsis_origin_url, offline=args.offline,
            )
            print(json.dumps({"manifest": str(path), "status": manifest["status"], "integrity": manifest["integrity"]}, indent=2))
            sys.exit(0 if manifest["status"] == "complete" else 2)
        manifest = json.loads(args.manifest.read_bytes())
        if args.command == "restore":
            result = restore_manifest(args.root, manifest)
            ok = result["verification"]["integrity_ok"]
        else:
            result = verify_manifest(args.root, manifest)
            ok = result["integrity_ok"]
        print(json.dumps(result, indent=2, sort_keys=True))
        sys.exit(0 if ok else 1)
    except (OSError, ValueError, KeyError) as error:
        LOGGER.error("%s", error)
        sys.exit(1)


if __name__ == "__main__":
    main()
