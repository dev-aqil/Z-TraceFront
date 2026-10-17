"""Integrity tests runnable with unittest or pytest without application services."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from tracefront_data.audit import audit_records, audit_snapshot, is_missing, sha256_file


class SnapshotAuditTests(unittest.TestCase):
    def test_missing_does_not_treat_zero_or_false_as_absent(self):
        for value in (None, "", "  ", [], {}):
            self.assertTrue(is_missing(value))
        for value in (0, False, "0", [0]):
            self.assertFalse(is_missing(value))

    def test_duplicate_and_missing_identifiers_are_distinct(self):
        rows = [{"recall_number": "R1", "event_id": "E1"}] * 2 + [{"event_id": "E1"}]
        result = audit_records(rows)
        self.assertEqual(result["exact_duplicate_rows"], 1)
        self.assertEqual(result["identifiers"]["recall_number"]["missing"], 1)
        self.assertEqual(result["identifiers"]["recall_number"]["duplicate_nonmissing_rows"], 1)
        self.assertEqual(result["identifiers"]["event_id"]["unique_nonmissing"], 1)
        self.assertEqual(result["rows_removed"], 0)

    def test_dates_flag_invalid_and_plausible_but_suspicious_years(self):
        values = ["20240229", "20230229", "02121207", "2024-01-01", 20240101, None]
        result = audit_records([{"report_date": value} for value in values])["dates"]["report_date"]
        self.assertEqual(result["invalid_count"], 3)
        self.assertEqual(result["pre_2000_count"], 1)
        self.assertEqual(result["parsed_min"], "0212-12-07")

    def test_empty_snapshot_and_malformed_results(self):
        self.assertEqual(audit_records([])["rows"], 0)
        for value in ({}, [1], None):
            with self.assertRaises(ValueError):
                audit_records(value)

    def test_snapshot_archive_match_and_source_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "snapshot.json"
            source.write_text(json.dumps({"meta": {}, "results": [{"event_id": "E"}]}))
            before = sha256_file(source)
            archive_path = Path(directory) / "snapshot.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.write(source, source.name)
            first = audit_snapshot(source, archive_path)
            self.assertTrue(first["archive"]["member_matches_input"])
            self.assertIsNone(first["archive"]["crc_error_member"])
            self.assertEqual(sha256_file(source), before)
            self.assertEqual(first, audit_snapshot(source, archive_path))
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(source.name, "different content")
            self.assertFalse(audit_snapshot(source, archive_path)["archive"]["member_matches_input"])

    def test_cli_rejects_overwriting_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "snapshot.json"
            source.write_text('{"results": []}')
            before = sha256_file(source)
            process = subprocess.run(
                [sys.executable, "-m", "tracefront_data.audit", "--input", str(source), "--output", str(source)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(process.returncode, 2)
            self.assertIn("must not overwrite", process.stderr)
            self.assertEqual(sha256_file(source), before)


if __name__ == "__main__":
    unittest.main()
