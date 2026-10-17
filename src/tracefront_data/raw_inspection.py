"""Read-only, source-specific M1 structural inspection; no cleaning or labels."""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
from typing import Any, TextIO
import xml.etree.ElementTree as ET
import zipfile

from tracefront_data.audit import audit_snapshot, sha256_file
from tracefront_data.provenance import inside_root, verify_manifest


def profile_delimited(stream: TextIO, *, columns: list[str] | None = None,
                      delimiter: str = ",", categories: tuple[str, ...] = (),
                      ranges: tuple[str, ...] = (), key: str | None = None) -> dict[str, Any]:
    reader = csv.reader(stream, delimiter=delimiter, strict=True)
    header = columns if columns is not None else next(reader)
    if not header or len(set(header)) != len(header):
        raise ValueError("Empty or repeated column names")
    positions = {c: header.index(c) for c in (*categories, *ranges, *((key,) if key else ()))}
    counts = {c: Counter() for c in categories}
    bounds: dict[str, list[str | None]] = {c: [None, None] for c in ranges}
    widths: Counter[int] = Counter()
    keys: Counter[str] = Counter()
    missing = Counter()
    rows = 0
    for row in reader:
        rows += 1
        widths[len(row)] += 1
        if len(row) != len(header):
            continue
        missing.update(c for c, value in zip(header, row) if value == "")
        for c in categories:
            counts[c][row[positions[c]]] += 1
        for c in ranges:
            value = row[positions[c]]
            if value:
                lo, hi = bounds[c]
                bounds[c] = [min(lo, value) if lo is not None else value,
                             max(hi, value) if hi is not None else value]
        if key:
            keys[row[positions[key]]] += 1
    return {"rows": rows, "columns": header, "column_count": len(header),
            "row_width_counts": dict(sorted(widths.items())),
            "malformed_width_rows": sum(n for w, n in widths.items() if w != len(header)),
            "empty_string_counts": dict(sorted(missing.items())),
            "raw_category_counts": {c: dict(sorted(v.items())) for c, v in counts.items()},
            "raw_lexical_ranges": bounds,
            "key": key, "unique_nonempty_keys": len(keys) - ("" in keys) if key else None,
            "missing_key_rows": keys.get("", 0) if key else None,
            "duplicate_key_extra_rows": sum(n - 1 for k, n in keys.items() if k and n > 1) if key else None,
            "_keys": set(keys)}


def zip_inventory(archive: zipfile.ZipFile) -> list[dict[str, Any]]:
    """Validate all compressed bytes by streaming, bounded before decompression."""
    members = archive.infolist()
    if len(members) > 1000 or sum(i.file_size for i in members) > 512 * 1024 * 1024:
        raise ValueError("Archive exceeds M1 member/expanded-size limits")
    if len({i.filename for i in members}) != len(members):
        raise ValueError("Archive contains duplicate member names")
    result = []
    for item in members:
        path = PurePosixPath(item.filename)
        if path.is_absolute() or ".." in path.parts or "\\" in item.filename:
            raise ValueError("Unsafe archive member path")
        digest = hashlib.sha256()
        size = 0
        with archive.open(item) as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        if size != item.file_size:
            raise ValueError("Archive member length mismatch")
        result.append({"filename": item.filename, "size_bytes": size,
                       "sha256": digest.hexdigest(), "crc_checked": True})
    return result


def inspect_reference_workbook(data: bytes) -> dict[str, Any]:
    """Inspect the small PDP code workbook, preserving strings and sparse cells.

    This is deliberately not a general spreadsheet importer: only raw cell text
    in this reference workbook is read. Styles/dates/formulas are not evaluated.
    """
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        zip_inventory(book)
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            shared = ["".join(si.itertext()) for si in ET.fromstring(book.read("xl/sharedStrings.xml")).findall("s:si", ns)]
        relationships = {r.attrib["Id"]: r.attrib["Target"] for r in ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))}
        result = {}
        for sheet in ET.fromstring(book.read("xl/workbook.xml")).findall("s:sheets/s:sheet", ns):
            target = relationships[sheet.attrib[f"{{{rel_ns}}}id"]]
            member = target.lstrip("/") if target.startswith("/") else "xl/" + target
            if ".." in PurePosixPath(member).parts:
                raise ValueError("Unsafe worksheet relationship")
            rows = []
            for row in ET.fromstring(book.read(member)).findall("s:sheetData/s:row", ns):
                cells = {}
                for cell in row.findall("s:c", ns):
                    value = cell.findtext("s:v", default="", namespaces=ns)
                    if cell.get("t") == "s":
                        value = shared[int(value)]
                    elif cell.get("t") == "inlineStr":
                        value = "".join(cell.find("s:is", ns).itertext())
                    cells[cell.attrib["r"]] = value
                if any(cells.values()):
                    rows.append(cells)
            # Full small vocabularies make the dictionary inspection auditable.
            result[sheet.attrib["name"]] = {"nonempty_rows_including_titles_headers": len(rows),
                                            "first_rows_raw_cells": rows[:15]}
        return result


def inspect_pdp(path: Path, schema: dict[str, Any]) -> dict[str, Any]:
    if schema.get("reviewed_archive_sha256") != sha256_file(path):
        raise ValueError("Annual dictionary mapping is not reviewed against this archive hash")
    with zipfile.ZipFile(path) as archive:
        members = zip_inventory(archive)
        for field in ("sample_member", "result_member", "dictionary_member", "reference_member"):
            archive.getinfo(schema[field])
        with io.TextIOWrapper(archive.open(schema["sample_member"]), encoding="utf-8", newline="") as stream:
            sample = profile_delimited(stream, columns=schema["sample_columns"], delimiter="|",
                                       categories=("STATE", "YEAR", "MONTH", "DAY", "ORIGIN", "COUNTRY", "COMMOD"),
                                       key="SAMPLE_PK")
        with io.TextIOWrapper(archive.open(schema["result_member"]), encoding="utf-8", newline="") as stream:
            result = profile_delimited(stream, columns=schema["result_columns"], delimiter="|",
                                       categories=("MEAN", "CONUNIT", "ANNOTATE"), key="SAMPLE_PK")
        unknown_keys = result.pop("_keys") - sample.pop("_keys")
        result["foreign_keys_absent_from_sample_table"] = sorted(unknown_keys)
        workbook = inspect_reference_workbook(archive.read(schema["reference_member"]))
    unknown_codes = sorted(set(result["raw_category_counts"]["MEAN"]) - schema["mean_code_meanings"].keys())
    return {"format": "ZIP: headerless pipe-delimited text + PDF/XLSX dictionaries + Access template",
            "row_granularity": schema["grain"], "members": members,
            "sample_table": sample, "result_table": result, "reference_workbook": workbook,
            "dictionary_mapping": schema, "unknown_mean_codes": unknown_codes,
            "structural_review_ok": not (sample["malformed_width_rows"] or result["malformed_width_rows"]
                or sample["duplicate_key_extra_rows"] or sample["missing_key_rows"]
                or result["missing_key_rows"] or unknown_keys or unknown_codes),
            "target": "Raw concentration / documented detection finding; regulatory exceedance remains conditional",
            "timestamps": ["YEAR", "MONTH", "DAY"],
            "identifiers": ["SAMPLE_PK (release-local)", "SITE (collection site, not farm/facility)", "LAB", "COMMOD", "PESTCODE"],
            "geography": "US sampling STATE; ORIGIN/COUNTRY and GROWST/PACKST/DISTST codes; not coordinates",
            "time_coverage": "2024 (raw YEAR/MONTH/DAY distributions recorded; no date normalization)",
            "schema_issues": ["Headerless file order from matching embedded annual dictionary; basename case differs in dictionary",
                "SAMPLE_PK only unique within annual release; results are one-to-many and sample/analyte uniqueness unproven",
                "Blank concentration denotes nondetect in annual text; ND and NP have distinct analytical quality meanings",
                "Tolerance workbook exists but has special strings/notes and requires effective-date/residue-definition review",
                "No safe/unsafe or chemical_exceedance label created; untested analytes absent"]}


def inspect_ghcn(path: Path, stations_path: Path) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    month_counts: Counter[str] = Counter()
    seen = set()
    duplicates = malformed = missing = populated = 0
    flags: Counter[str] = Counter()
    with path.open(encoding="ascii", newline="") as stream:
        for raw in stream:
            line = raw.rstrip("\r\n")
            if len(line) != 269:
                malformed += 1
                continue
            station, year, month, element = line[:11], line[11:15], line[15:17], line[17:21]
            key = (station, year, month, element)
            duplicates += key in seen
            seen.add(key)
            counts[element] += 1
            month_counts[year + "-" + month] += 1
            for offset in range(21, 269, 8):
                value = line[offset:offset + 5]
                if value == "-9999":
                    missing += 1
                else:
                    int(value)  # validate raw numeric format, without rescaling
                    populated += 1
                flags[line[offset + 6]] += 1
    ids = sorted({k[0] for k in seen})
    # Global station names contain UTF-8 characters despite the legacy fixed
    # layout; the selected Malaysian station line itself uses ASCII characters.
    with stations_path.open(encoding="utf-8") as station_stream:
        station_lines = [line.rstrip("\n") for line in station_stream if line[:11] in ids]
    return {"format": "GHCN-Daily fixed-width ASCII; 269 characters plus newline",
            "rows": sum(counts.values()) + malformed,
            "row_granularity": "station x year x month x weather element, with 31 day value/measurement/quality/source slots",
            "columns": ["ID", "YEAR", "MONTH", "ELEMENT", "VALUE1..31", "MFLAG1..31", "QFLAG1..31", "SFLAG1..31"],
            "identifiers": ids, "timestamps": ["YEAR", "MONTH", "day slot 1..31"],
            "geography": "Single Malaysian airport station; current official station line retained below",
            "official_station_lines": station_lines, "time_coverage": [min(month_counts), max(month_counts)],
            "element_month_row_counts": dict(sorted(counts.items())),
            "sentinel_day_slots_including_noncalendar_padding": missing,
            "populated_day_slots": populated, "quality_flag_slot_counts": dict(sorted(flags.items())),
            "duplicate_station_month_element_rows": duplicates, "malformed_width_rows": malformed,
            "structural_review_ok": not (duplicates or malformed) and len(station_lines) == len(ids),
            "target": None,
            "schema_issues": ["31-day slots include invalid calendar days as -9999 padding; not all slots are observations",
                "TMIN/TMAX/TAVG are tenths Celsius and PRCP tenths mm in raw .dly; other elements have distinct units",
                "Nonblank quality flags need exclusion/review in M2; blanks do not prove perfect measurements",
                "One station is not national coverage, a farm location, or an FSIS weather join",
                "Station-month counts differ by element; earliest/latest month is not continuous daily completeness",
                "Downloaded global station inventory contains UTF-8 station names; .dly weather values are ASCII"]}


def m2_gate(source: dict, inspection: dict, artifacts: list[dict]) -> dict[str, bool]:
    return {"provenance_confirmed": source.get("provenance_confirmed") is True,
            "license_known": source.get("license_known") is True and bool(source.get("license")),
            "raw_data_present_and_hash_pinned": any(a["status"] == "captured" and a["role"] in {"data", "context_data"}
                                                    and a.get("sha256") and a.get("size_bytes", 0) > 0 for a in artifacts),
            "row_granularity_understood": bool(inspection.get("row_granularity")),
            "schema_review_passed": inspection.get("structural_review_ok") is True,
            "schema_issues_documented": bool(inspection.get("schema_issues"))}


def inspect_manifest(root: Path, manifest: dict) -> dict:
    integrity = verify_manifest(root, manifest)
    if not integrity["integrity_ok"]:
        raise ValueError(f"Artifact integrity failed: {integrity}")
    output = {"milestone": "M1", "status": "partial", "integrity": integrity,
              "receipt_created_at": manifest["created_at"],
              "config_sha256": manifest["config_sha256"], "datasets": {}}
    for name, source in manifest["datasets"].items():
        dataset = {k: v for k, v in source.items() if k not in {"artifacts", "schema"}}
        artifacts = source["artifacts"]
        by_id = {a["artifact_id"]: inside_root(root, a["path"]) for a in artifacts if a["status"] == "captured"}
        inspection: dict[str, Any] = {}
        try:
            if name == "usda_pdp" and "pdp_2024" in by_id:
                inspection = inspect_pdp(by_id["pdp_2024"], source["schema"])
            elif name.startswith("opendosm_"):
                table = name.removeprefix("opendosm_")
                if table in by_id:
                    with by_id[table].open(encoding="utf-8", newline="") as stream:
                        inspection = profile_delimited(stream, categories=("state", "crop_type"), ranges=("date",))
                    inspection.pop("_keys")
                    inspection.update(format="CSV with header, UTF-8", row_granularity=(
                        "year x state/country x crop type" if table == "crops_state" else "year x state x district x crop type x species"),
                        identifiers=[c for c in inspection["columns"] if c not in {"date", "production", "planted_area"}],
                        timestamps=["date (annual reference year, not publication instant)"],
                        geography="Malaysia; state/district names and national aggregates where present",
                        time_coverage=inspection["raw_lexical_ranges"]["date"], target=None,
                        structural_review_ok=not inspection["malformed_width_rows"],
                        schema_issues=source["limitations"])
            elif name == "noaa_ghcn_daily" and "ghcn_station_data" in by_id:
                inspection = inspect_ghcn(by_id["ghcn_station_data"], by_id["ghcn_stations"])
                inspection["release_status_text"] = by_id["ghcn_version"].read_text()
            elif name == "openfda_enforcement":
                inspection = audit_snapshot(by_id["openfda_local_json"], by_id["openfda_local_zip"])
                official_match = sha256_file(by_id["openfda_upstream_zip"]) == sha256_file(by_id["openfda_local_zip"])
                inspection["official_archive_matches_local_archive"] = official_match
                inspection["input_path"] = by_id["openfda_local_json"].relative_to(root).as_posix()
                inspection["archive"]["input_path"] = by_id["openfda_local_zip"].relative_to(root).as_posix()
                inspection.update(row_granularity="product-specific recall enforcement record; multiple products can share event_id",
                                  structural_review_ok=official_match and inspection["archive"]["member_matches_input"] and inspection["archive"]["crc_error_member"] is None,
                                  schema_issues=source["limitations"] + [
                                      "One missing recall_number; initiation-date year 0212 is retained unchanged"],
                                  timestamps=["report_date", "recall_initiation_date", "center_classification_date", "termination_date"],
                                  identifiers=["recall_number (one missing)", "event_id", "recalling_firm (name, no verified facility ID)"],
                                  geography="Recalling-firm country/state/city/postal address plus textual distribution",
                                  time_coverage="report_date 2012-06-20..2026-10-07", target=None)
        except (ValueError, KeyError, OSError, zipfile.BadZipFile, csv.Error, ET.ParseError, UnicodeError) as error:
            inspection = {"structural_review_ok": False, "inspection_error": str(error), "error_type": type(error).__name__}
        gate = m2_gate(source, inspection, artifacts)
        dataset.update(artifacts=artifacts, inspection=inspection, m2_gate=gate, m2_eligible=all(gate.values()),
                       acquisition_status="acquired" if gate["raw_data_present_and_hash_pinned"] else "pending")
        if name == "fsis_raw_poultry":
            dataset["source_status"] = "official source confirmed, raw file not yet acquired"
        output["datasets"][name] = dataset
    return output
