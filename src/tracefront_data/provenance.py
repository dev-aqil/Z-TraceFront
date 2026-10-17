"""Immutable artifact capture and verification using only the standard library."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, BinaryIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from tracefront_data.audit import sha256_file


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def validate_timestamp(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("retrieval timestamp must include its timezone")
    if parsed > datetime.now(timezone.utc):
        raise ValueError("retrieval timestamp must not be in the future")
    return parsed.astimezone(timezone.utc).isoformat()


def safe_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,150}", value):
        raise ValueError(f"unsafe artifact name: {value!r}")
    return value


def safe_filename(value: str) -> str:
    """Keep original publisher basenames, including spaces, without path components."""
    if (not value.strip() or value in {".", ".."} or "/" in value or "\\" in value
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
            or len(value.encode("utf-8")) > 255):
        raise ValueError(f"unsafe artifact filename: {value!r}")
    return value


def inside_root(root: Path, relative: str) -> Path:
    path = root / relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("artifact paths must stay inside the project root")
    return path


def publish_stream(
    stream: BinaryIO, *, root: Path, directory: str, filename: str,
    expected_sha256: str | None = None, max_bytes: int = 256 * 1024 * 1024,
    expected_size: int | None = None,
) -> dict[str, Any]:
    """Publish complete validated bytes once; refuse to overwrite existing content.

    Temporary and destination files share a filesystem. A hard link publishes
    atomically without replacing an existing artifact, including concurrent runs.
    Read-only permissions discourage edits; hashes detect later tampering.
    """
    safe_filename(filename)
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if expected_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("expected SHA-256 must be 64 lowercase hexadecimal digits")
    base = inside_root(root, directory)
    base.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=base, prefix=".partial-", delete=False) as output:
            temporary = Path(output.name)
            digest = hashlib.sha256()
            size = 0
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError(f"artifact exceeds {max_bytes} byte intake limit")
                digest.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        checksum = digest.hexdigest()
        if size == 0:
            raise ValueError("empty artifact")
        if expected_size is not None and size != expected_size:
            raise ValueError(f"truncated/unexpected response: expected {expected_size} bytes, received {size}")
        if expected_sha256 is not None and checksum != expected_sha256:
            raise ValueError("SHA-256 does not match the frozen source expectation")
        destination = base / "sha256" / checksum / filename
        inside_root(root, destination.relative_to(root).as_posix())
        destination.parent.mkdir(parents=True, exist_ok=True)
        reused = False
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if destination.is_symlink() or not destination.is_file() or sha256_file(destination) != checksum:
                raise ValueError("existing immutable artifact is corrupt or is a symlink")
            reused = True
        destination.chmod(0o444)
        return {
            "path": destination.relative_to(root).as_posix(),
            "size_bytes": size, "sha256": checksum, "reused": reused,
        }
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def capture_artifact(spec: dict[str, Any], root: Path, directory: str) -> dict[str, Any]:
    """Capture a local import or HTTPS response, keeping failed attempts explicit.

    Imported files are never described as freshly downloaded. HTTP metadata is
    advisory, not proof of historical availability or a vendor-issued checksum.
    """
    started = utc_now()
    kind = "download" if "url" in spec else "local_import"
    record: dict[str, Any] = {
        "artifact_id": spec["artifact_id"], "role": spec["role"],
        "method": kind, "source_url": spec.get("url"),
        "source_path": spec.get("local_path"),
        "source_reference_url": spec.get("source_reference_url"),
        "declared_download_url": spec.get("declared_download_url"),
        "source_version": spec.get("source_version"),
        "expected_sha256": spec.get("expected_sha256"),
        "retrieved_at": None, "imported_at": None, "attempted_at": started,
    }
    try:
        kwargs = dict(root=root, directory=directory, filename=spec["filename"],
                      expected_sha256=spec.get("expected_sha256"),
                      max_bytes=spec.get("max_bytes", 256 * 1024 * 1024))
        if kind == "download":
            url = spec["url"]
            if urlsplit(url).scheme != "https":
                raise ValueError("source downloads require HTTPS")
            request = Request(url, headers={
                "User-Agent": "TracefrontData/0.1 (public research data ingestion)",
                "Accept-Encoding": "identity",
            })
            with urlopen(request, timeout=30) as response:
                if urlsplit(response.geturl()).scheme != "https":
                    raise ValueError("source redirected away from HTTPS")
                content_length = response.headers.get("Content-Length")
                record.update({
                    "resolved_url": response.geturl(), "http_status": response.status,
                    "content_type": response.headers.get("Content-Type"),
                    "http_etag": response.headers.get("ETag"),
                    "http_last_modified": response.headers.get("Last-Modified"),
                })
                record.update(publish_stream(response, expected_size=int(content_length) if content_length else None, **kwargs))
            record["retrieved_at"] = utc_now()
        else:
            original_retrieval = validate_timestamp(spec.get("retrieved_at"))
            source = inside_root(root, spec["local_path"])
            with source.open("rb") as stream:
                record.update(publish_stream(stream, **kwargs))
            record["retrieved_at"] = original_retrieval
            record["imported_at"] = utc_now()
        record["status"] = "captured"
    except (OSError, URLError, HTTPException, ValueError) as error:
        record.update(status="failed", error_type=type(error).__name__, error=str(error))
        if isinstance(error, HTTPError):
            record["http_status"] = error.code
    return record


def write_manifest(root: Path, manifest: dict[str, Any]) -> Path:
    """Append a new receipt, never overwrite a prior run's metadata."""
    directory = inside_root(root, "data/manifests")
    directory.mkdir(parents=True, exist_ok=True)
    name = safe_name(manifest["run_id"]) + ".json"
    path = directory / name
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".partial-", mode="w", encoding="utf-8", delete=False) as output:
            temporary = Path(output.name)
            json.dump(manifest, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        temporary.chmod(0o444)
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def verify_manifest(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Check every captured artifact; failed acquisitions remain separate gaps."""
    failures: list[dict[str, str]] = []
    checked = 0
    for dataset in manifest["datasets"].values():
        for artifact in dataset["artifacts"]:
            if artifact["status"] != "captured":
                continue
            checked += 1
            try:
                path = inside_root(root, artifact["path"])
                if path.is_symlink() or path.stat().st_size != artifact["size_bytes"] or sha256_file(path) != artifact["sha256"]:
                    raise ValueError("artifact bytes differ from manifest")
            except (OSError, ValueError) as error:
                failures.append({"artifact_id": artifact["artifact_id"], "error": str(error)})
    return {"checked_artifacts": checked, "integrity_ok": not failures, "failures": failures,
            "acquisition_status": manifest["status"]}
