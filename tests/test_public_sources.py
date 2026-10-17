"""M1 regression checks; every data fixture in this file is synthetic."""

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tracefront_data.provenance import capture_artifact, write_manifest
from tracefront_data.public_sources import acquire, capture_or_reuse
from tracefront_data.raw_inspection import inspect_ghcn, inspect_manifest, inspect_pdp, m2_gate, profile_delimited, zip_inventory


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_raw_csv_retains_ids_blanks_and_malformed_rows(self):
        content = "id,code,date\n001, ,2024-01-01\n002,,2024-01-02\n003,ND\n"
        result = profile_delimited(io.StringIO(content), categories=("code",), ranges=("date",), key="id")
        self.assertEqual(result["rows"], 3)
        self.assertEqual(result["malformed_width_rows"], 1)
        self.assertEqual(result["_keys"], {"001", "002"})
        self.assertEqual(result["raw_category_counts"]["code"], {" ": 1, "": 1})

    def test_archive_paths_and_duplicate_names_rejected(self):
        for names in (["../outside.txt"], ["/absolute"], ["a\\b"]):
            data = io.BytesIO()
            with zipfile.ZipFile(data, "w") as archive:
                for name in names:
                    archive.writestr(name, b"fixture")
            with zipfile.ZipFile(data) as archive:
                with self.assertRaises(ValueError):
                    zip_inventory(archive)

    def test_member_hash_and_crc_are_measured(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("original name.txt", b"unchanged fixture bytes")
        with zipfile.ZipFile(data) as archive:
            member = zip_inventory(archive)[0]
        self.assertEqual(member["sha256"], hashlib.sha256(b"unchanged fixture bytes").hexdigest())
        self.assertTrue(member["crc_checked"])

    def test_pdp_dictionary_mapping_rejects_unreviewed_archive(self):
        path = self.root / "fixture.zip"
        path.write_bytes(b"different release")
        with self.assertRaisesRegex(ValueError, "not reviewed"):
            inspect_pdp(path, {"reviewed_archive_sha256": "0" * 64})

    @patch("tracefront_data.raw_inspection.inspect_reference_workbook", return_value={"synthetic": {}})
    def test_pdp_unknown_result_code_and_orphan_sample_fail_review(self, _workbook):
        config_path = Path(__file__).parents[1] / "configs/m1_public_sources.json"
        schema = json.loads(config_path.read_text())["datasets"]["usda_pdp"]["schema"].copy()
        sample = {"SAMPLE_PK": "001", "STATE": "CA", "YEAR": "24", "MONTH": "01", "DAY": "02",
                  "ORIGIN": "1", "COMMOD": "XX"}
        results = [{"SAMPLE_PK": "001", "MEAN": "ND", "CONCEN": "", "CONUNIT": "M"},
                   {"SAMPLE_PK": "999", "MEAN": "UNREVIEWED", "CONCEN": "0.1", "CONUNIT": "M"}]
        path = self.root / "synthetic.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(schema["sample_member"], "|".join(sample.get(c, "") for c in schema["sample_columns"]) + "\n")
            archive.writestr(schema["result_member"], "".join("|".join(r.get(c, "") for c in schema["result_columns"]) + "\n" for r in results))
            archive.writestr(schema["dictionary_member"], b"synthetic dictionary placeholder")
            archive.writestr(schema["reference_member"], b"synthetic workbook placeholder, parser mocked")
        schema["reviewed_archive_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        before = path.read_bytes()
        result = inspect_pdp(path, schema)
        self.assertFalse(result["structural_review_ok"])
        self.assertEqual(result["result_table"]["foreign_keys_absent_from_sample_table"], ["999"])
        self.assertEqual(result["unknown_mean_codes"], ["UNREVIEWED"])
        self.assertEqual(result["result_table"]["empty_string_counts"]["CONCEN"], 1)
        self.assertEqual(path.read_bytes(), before)

    def test_weather_granularity_padding_and_utf8_station_names(self):
        path = self.root / "station.dly"
        # One real day slot and 30 sentinel slots, not 31 daily observations.
        line = "MYM00048647" + "2024" + "02" + "TMAX" + "  302 KX" + "-9999   " * 30
        self.assertEqual(len(line), 269)
        path.write_text(line + "\n")
        stations = self.root / "stations.txt"
        stations.write_text("ZZ000000000 Cité\nMYM00048647 synthetic selected station\n", encoding="utf-8")
        result = inspect_ghcn(path, stations)
        self.assertEqual(result["rows"], 1)
        self.assertEqual(result["populated_day_slots"], 1)
        self.assertEqual(result["sentinel_day_slots_including_noncalendar_padding"], 30)
        self.assertEqual(result["quality_flag_slot_counts"]["K"], 1)
        self.assertTrue(result["structural_review_ok"])

    def test_every_m2_gate_is_required_and_metadata_is_not_data(self):
        source = {"provenance_confirmed": True, "license_known": True, "license": "synthetic test license"}
        inspected = {"row_granularity": "synthetic sample", "structural_review_ok": True, "schema_issues": ["fixture only"]}
        artifact = {"status": "captured", "role": "data", "sha256": "1" * 64, "size_bytes": 5}
        self.assertTrue(all(m2_gate(source, inspected, [artifact]).values()))
        for change in ({"license_known": False}, {"provenance_confirmed": False}, {"license": None}):
            self.assertFalse(all(m2_gate(source | change, inspected, [artifact]).values()))
        for change in ({"row_granularity": None}, {"structural_review_ok": False}, {"schema_issues": []}):
            self.assertFalse(all(m2_gate(source, inspected | change, [artifact]).values()))
        for change in ({"role": "documentation"}, {"status": "failed"}, {"sha256": None}, {"size_bytes": 0}):
            self.assertFalse(all(m2_gate(source, inspected, [artifact | change]).values()))

    def test_reuse_preserves_retrieval_and_detects_corruption(self):
        path = self.root / "original.csv"
        path.write_bytes(b"x\n1\n")
        record = capture_artifact({"artifact_id": "test", "role": "data", "filename": path.name,
                                   "local_path": path.name}, self.root, "data/raw/source")
        record.update(source_url="https://example.gov/original.csv", retrieved_at="2024-01-01T00:00:00+00:00")
        spec = {"url": record["source_url"], "reuse_artifact": record}
        result = capture_or_reuse(spec, self.root, "data/raw/source")
        self.assertEqual(result["retrieved_at"], record["retrieved_at"])
        stored = self.root / result["path"]
        stored.chmod(0o644)
        stored.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "corrupt"):
            capture_or_reuse(spec, self.root, "data/raw/source")

    def test_failed_source_does_not_stop_other_sources(self):
        config = self.root / "config.json"
        config.write_text(json.dumps({"datasets": {name: {"directory": "data/raw/" + name,
            "artifacts": [{"artifact_id": name, "role": "data", "filename": name + ".csv",
                           "local_path": name + ".csv"}]} for name in ["missing", "present"]}}))
        (self.root / "present.csv").write_bytes(b"id\n001\n")
        receipt = json.loads(acquire(self.root, config).read_text())
        self.assertEqual(receipt["datasets"]["missing"]["artifacts"][0]["status"], "failed")
        self.assertEqual(receipt["datasets"]["present"]["artifacts"][0]["status"], "captured")
        with self.assertRaises(FileExistsError):
            write_manifest(self.root, receipt)

    def test_integrity_failure_prevents_eligibility_inspection(self):
        manifest = {"status": "partial", "datasets": {"fixture": {"artifacts": [
            {"artifact_id": "test", "status": "captured", "path": "absent.csv", "size_bytes": 1, "sha256": "0" * 64}]}}}
        with self.assertRaisesRegex(ValueError, "integrity"):
            inspect_manifest(self.root, manifest)


if __name__ == "__main__":
    unittest.main()
