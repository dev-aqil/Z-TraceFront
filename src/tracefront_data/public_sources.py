"""M1 acquisition of official public sources; no preparation or joins.

Raw bytes use the existing immutable store. Receipts append; inspection reports
can be regenerated offline. Source failures do not stop unrelated acquisitions.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from tracefront_data.audit import sha256_file
from tracefront_data.provenance import capture_artifact, inside_root, utc_now, verify_manifest, write_manifest


def capture_or_reuse(spec: dict, root: Path, directory: str) -> dict:
    if "reuse_artifact" not in spec:
        return capture_artifact(spec, root, directory)
    record = spec["reuse_artifact"].copy()
    if record.get("source_url") != spec["url"]:
        raise ValueError("Reuse URL differs from acquisition specification")
    if spec.get("expected_sha256") not in (None, record.get("sha256")):
        raise ValueError("Reuse hash differs from frozen source expectation")
    check = verify_manifest(root, {"datasets": {"source": {"artifacts": [record]}}, "status": "partial"})
    if record["status"] != "captured" or not check["integrity_ok"]:
        raise ValueError("Cannot reuse absent/corrupt source artifact")
    record["reuse_verified_at"] = utc_now()
    return record


def acquire(root: Path, config_path: Path, selected: list[str] | None = None) -> Path:
    config = json.loads(config_path.read_text())
    if selected and set(selected) - config["datasets"].keys():
        raise ValueError("Unknown --source")
    manifest = {"run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8],
                "created_at": utc_now(), "milestone": "M1", "status": "partial",
                "config_sha256": sha256_file(config_path), "source_config": config,
                "pipeline_code_sha256": {p.name: sha256_file(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
                "datasets": {}}
    for name, source in config["datasets"].items():
        if selected and name not in selected:
            continue
        print(f"Acquiring {name}", flush=True)
        dataset = {k: v for k, v in source.items() if k != "artifacts"}
        if "reuse_manifest" in source:
            previous = json.loads(inside_root(root, source["reuse_manifest"]).read_text())
            prior = previous["datasets"][name]
            check = verify_manifest(root, {"datasets": {name: prior}, "status": "partial"})
            if not check["integrity_ok"]:
                raise ValueError(f"Prior source receipt failed integrity: {check}")
            dataset["artifacts"] = prior["artifacts"]
            dataset["prior_inspection"] = prior.get("inspection", {})
            if name == "openfda_enforcement":
                dataset["inspection"] = prior.get("inspection", {})
            dataset["reuse_verified_at"] = utc_now()
        else:
            with ThreadPoolExecutor(max_workers=4) as pool:
                dataset["artifacts"] = list(pool.map(
                    lambda spec: capture_or_reuse(spec, root, source["directory"]), source["artifacts"]))
        manifest["datasets"][name] = dataset
        for artifact in dataset["artifacts"]:
            print(f"  {artifact['artifact_id']}: {artifact['status']} "
                  f"{artifact.get('size_bytes', artifact.get('error', ''))}", flush=True)
    path = write_manifest(root, manifest)
    print(path.relative_to(root), flush=True)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["acquire", "inspect", "verify", "restore"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("configs/m1_public_sources.json"))
    parser.add_argument("--source", action="append")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/m1_source_manifest.json"))
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "acquire":
        acquire(root, inside_root(root, str(args.config)), args.source)
    else:
        if not args.manifest:
            parser.error("--manifest is required")
        manifest = json.loads(inside_root(root, str(args.manifest)).read_text())
        if args.command == "verify":
            result = verify_manifest(root, manifest)
            print(json.dumps(result, indent=2))
            if not result["integrity_ok"]:
                raise SystemExit(1)
        elif args.command == "restore":
            from tracefront_data.ingest import restore_manifest
            print(json.dumps(restore_manifest(root, manifest), indent=2))
        else:
            from tracefront_data.raw_inspection import inspect_manifest
            result = inspect_manifest(root, manifest)
            result["receipt"] = str(args.manifest)
            result["receipt_sha256"] = sha256_file(root / args.manifest)
            result["inspection_code_sha256"] = {
                p.name: sha256_file(p) for p in sorted(Path(__file__).parent.glob("*.py"))}
            output = inside_root(root, str(args.output))
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            print(output.relative_to(root))


if __name__ == "__main__":
    main()
