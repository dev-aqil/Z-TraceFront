"""M1 integrity/intake tests. Fixture observations are synthetic, never research data."""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from tracefront_data.audit import sha256_file
from tracefront_data.fsis import inspect_fsis, profile_rows
from tracefront_data.ingest import restore_manifest, run_ingestion
from tracefront_data.provenance import capture_artifact, publish_stream, verify_manifest, write_manifest


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def publish(self, content=b"official bytes", **kwargs):
        return publish_stream(io.BytesIO(content), root=self.root, directory="data/raw/fsis", filename="release.json", **kwargs)

    def test_repeated_capture_reuses_identical_bytes(self):
        first = self.publish()
        second = self.publish()
        self.assertEqual(first["path"], second["path"])
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])

    def test_hash_mismatch_truncation_and_size_limit_do_not_publish(self):
        for kwargs in ({"expected_sha256": "0" * 64}, {"expected_size": 999}, {"max_bytes": 2}):
            with self.assertRaises(ValueError):
                self.publish(**kwargs)
        self.assertEqual(list(self.root.rglob("release.json")), [])
        self.assertEqual(list(self.root.rglob(".partial-*")), [])

    def test_existing_corrupt_artifact_is_not_overwritten(self):
        artifact = self.publish()
        path = self.root / artifact["path"]
        path.chmod(0o644)
        path.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "corrupt"):
            self.publish()
        self.assertEqual(path.read_bytes(), b"tampered")

    def test_path_traversal_and_bad_hash_rejected(self):
        for kwargs in ({"directory": "../escape", "filename": "safe.json"}, {"directory": "data", "filename": "../bad.json"}):
            with self.assertRaises(ValueError):
                publish_stream(io.BytesIO(b"x"), root=self.root, **kwargs)
        with self.assertRaises(ValueError):
            self.publish(expected_sha256="bad")

    def test_manual_import_preserves_source_and_unknown_original_time(self):
        source = self.root / "release.json"
        source.write_bytes(b'{"data": []}')
        before = sha256_file(source)
        record = capture_artifact({"artifact_id": "fsis_data", "role": "source", "filename": source.name,
                                   "local_path": source.name}, self.root, "data/raw/fsis")
        self.assertEqual(record["status"], "captured")
        self.assertIsNone(record["retrieved_at"])
        self.assertIsNotNone(record["imported_at"])
        self.assertIsNone(record["source_url"])
        self.assertEqual(before, sha256_file(source))
        self.assertEqual(before, sha256_file(self.root / record["path"]))

    def test_publisher_filename_with_spaces_is_preserved(self):
        source = self.root / "Synthetic Poultry Release.JSON"
        source.write_bytes(b'[{"fixture":true}]')
        artifact = capture_artifact({"artifact_id": "fsis_data", "role": "synthetic_fixture",
                                    "filename": source.name, "local_path": source.name}, self.root, "data/raw/fsis")
        self.assertEqual(artifact["status"], "captured")
        self.assertEqual(Path(artifact["path"]).name, source.name)
        self.assertEqual(sha256_file(source), artifact["sha256"])

    def test_invalid_manual_retrieval_time_rejected_before_capture(self):
        source = self.root / "release.json"
        source.write_bytes(b"x")
        record = capture_artifact({"artifact_id": "a", "role": "data", "filename": source.name,
                                   "local_path": source.name, "retrieved_at": "2025-01-01T00:00:00"}, self.root, "data")
        self.assertEqual(record["status"], "failed")
        self.assertNotIn("path", record)

    @patch("tracefront_data.provenance.urlopen")
    def test_http_403_is_recorded_without_fabricated_data(self, mocked):
        url = "https://www.fsis.usda.gov/official.json"
        mocked.side_effect = HTTPError(url, 403, "Forbidden", {}, None)
        record = capture_artifact({"artifact_id": "fsis_data", "role": "source", "filename": "official.json", "url": url}, self.root, "data")
        self.assertEqual(record["http_status"], 403)
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["source_url"], url)
        self.assertIsNone(record["retrieved_at"])
        self.assertNotIn("path", record)

    @patch("tracefront_data.provenance.urlopen")
    def test_https_download_records_headers_time_and_exact_bytes(self, mocked):
        response = io.BytesIO(b'{"data": []}')
        response.status = 200
        response.headers = {"Content-Length": "12", "Content-Type": "application/json", "ETag": '"v1"'}
        response.geturl = lambda: "https://www.fsis.usda.gov/release.json"
        mocked.return_value = response
        record = capture_artifact({"artifact_id": "a", "role": "source", "filename": "release.json",
                                   "url": response.geturl()}, self.root, "data")
        self.assertEqual(record["status"], "captured")
        self.assertEqual(record["http_etag"], '"v1"')
        self.assertIsNotNone(record["retrieved_at"])
        self.assertIsNone(record["imported_at"])
        self.assertEqual((self.root / record["path"]).read_bytes(), b'{"data": []}')

    def test_manifest_verification_detects_missing_and_changed_bytes(self):
        artifact = {"artifact_id": "a", "status": "captured", **self.publish()}
        manifest = {"run_id": "test-run", "status": "partial", "datasets": {"fsis": {"artifacts": [artifact]}}}
        path = write_manifest(self.root, manifest)
        self.assertTrue(verify_manifest(self.root, manifest)["integrity_ok"])
        with self.assertRaises(FileExistsError):
            write_manifest(self.root, manifest)
        self.assertEqual(json.loads(path.read_bytes()), manifest)
        data = self.root / artifact["path"]
        data.chmod(0o644)
        data.write_bytes(b"changed")
        self.assertFalse(verify_manifest(self.root, manifest)["integrity_ok"])
        data.unlink()
        self.assertFalse(verify_manifest(self.root, manifest)["integrity_ok"])

    def test_restore_uses_frozen_hash(self):
        source = self.root / "original.json"
        source.write_bytes(b"source")
        spec = {"artifact_id": "a", "role": "source", "filename": source.name, "local_path": source.name}
        artifact = capture_artifact(spec, self.root, "data/raw/fsis")
        manifest = {"run_id": "parent", "status": "partial", "datasets": {"fsis": {"artifacts": [artifact]}},
                    "source_config": {"datasets": {"fsis": {"directory": "data/raw/fsis"}}}}
        destination = self.root / artifact["path"]
        destination.unlink()
        result = restore_manifest(self.root, manifest)
        self.assertTrue(result["verification"]["integrity_ok"])
        destination.unlink()
        source.write_bytes(b"newer upstream")
        result = restore_manifest(self.root, manifest)
        self.assertFalse(result["verification"]["integrity_ok"])
        self.assertFalse(destination.exists())

    @patch("tracefront_data.provenance.urlopen")
    def test_fresh_clone_restores_json_from_verified_official_zip(self, mocked):
        import zipfile
        source = self.root / "context.json"
        source.write_bytes(b'{"results": []}')
        archive = self.root / "context.json.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.write(source, source.name)
        def local(artifact_id, path):
            return capture_artifact({"artifact_id": artifact_id, "role": "fixture", "filename": path.name,
                                     "local_path": path.name}, self.root, "data/external/openfda")
        json_artifact = local("openfda_local_json", source)
        zip_artifact = local("openfda_local_zip", archive)
        upstream = {**zip_artifact, "artifact_id": "openfda_upstream_zip", "method": "download",
                    "source_path": None, "source_url": "https://download.open.fda.gov/official.zip"}
        manifest = {"run_id": "verified-parent", "status": "partial", "source_config": {
            "datasets": {"openfda_enforcement": {"directory": "data/external/openfda"}}}, "datasets": {
            "openfda_enforcement": {"artifacts": [json_artifact, zip_artifact, upstream],
                "inspection": {"official_archive_matches_local_archive": True}}}}
        before = json.dumps(manifest, sort_keys=True)
        response = io.BytesIO(archive.read_bytes())
        response.status = 200
        response.headers = {"Content-Length": str(archive.stat().st_size)}
        response.geturl = lambda: upstream["source_url"]
        mocked.return_value = response
        with tempfile.TemporaryDirectory() as empty_directory:
            target = Path(empty_directory)
            result = restore_manifest(target, manifest)
            self.assertTrue(result["verification"]["integrity_ok"])
            self.assertEqual((target / json_artifact["path"]).read_bytes(), source.read_bytes())
            self.assertEqual(result["restored_attempts"][-1]["method"], "verified_archive_member_replay")
            self.assertTrue(Path(result["restoration_receipt"]).is_file())
        self.assertEqual(before, json.dumps(manifest, sort_keys=True))
        mocked.assert_called_once()


class FSISInspectionTests(unittest.TestCase):
    def setUp(self):
        self.contract = {
            "mapping_reviewed": True, "identity_columns": ["sample"],
            "fields": {"result": "result", "collection_date": "date"},
            "cohort_filters": {"program": "one"},
            "result_codes": {"positive": ["P"], "negative": ["N"], "untested": ["NT"], "indeterminate": ["I"]},
        }
        self.rows = [{"sample": str(i), "program": "one", "date": "2025-01-01", "result": value}
                     for i, value in enumerate(["P", "N", "NT", "I", None, "", "NEW"])]

    def test_positive_negative_untested_unknown_remain_distinct(self):
        result = profile_rows(self.rows, self.contract)
        self.assertEqual(result["cohort_code_interpretation_counts"], {"positive": 1, "negative": 1, "untested": 1, "indeterminate": 1})
        self.assertEqual(result["cohort_unmapped_codes"], {'null': 1, '""': 1, '"NEW"': 1})
        self.assertEqual(result["readiness"], "review_required")
        self.assertFalse(result["training_eligible"])

    def test_exact_filters_and_duplicate_sample_keys(self):
        rows = [self.rows[0], self.rows[0], {**self.rows[1], "program": "other"}]
        result = profile_rows(rows, self.contract)
        self.assertEqual(result["selected_rows"], 2)
        self.assertEqual(result["unique_populated_keys"], 1)
        self.assertEqual(result["duplicate_populated_key_rows"], 1)

    def test_unreviewed_contract_does_not_claim_a_cohort(self):
        result = profile_rows(self.rows, {"mapping_reviewed": False})
        self.assertIsNone(result["selected_rows"])
        self.assertIsNone(result["cohort_code_interpretation_counts"])

    def test_conflicting_codes_and_absent_fields_fail(self):
        self.contract["result_codes"]["negative"] = ["P"]
        with self.assertRaises(ValueError):
            profile_rows(self.rows, self.contract)
        self.contract["result_codes"]["negative"] = ["N"]
        self.contract["fields"]["result"] = "nonexistent"
        with self.assertRaises(ValueError):
            profile_rows(self.rows, self.contract)

    def test_missing_result_cannot_be_configured_as_a_negative(self):
        for value in (None, "", "  "):
            self.contract["result_codes"]["negative"] = [value]
            with self.assertRaisesRegex(ValueError, "missing/blank"):
                profile_rows(self.rows, self.contract)

    def test_json_ambiguous_dictionary_array_requires_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "official.json"
            path.write_text(json.dumps({"data": self.rows, "dictionary": [{"name": "result"}]}))
            result = inspect_fsis(path, self.contract)
            self.assertEqual(result["readiness"], "records_pointer_required")
            result = inspect_fsis(path, {**self.contract, "records_pointer": "/data"})
            self.assertEqual(result["source_rows"], 7)

    def test_catalog_distribution_is_not_a_sample_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps({"@type": "dcat:Dataset", "identifier": "usda-fsis-105",
                                       "distribution": [{"accessURL": "https://www.fsis.usda.gov/official"}]}))
            with self.assertRaisesRegex(ValueError, "catalog metadata is not"):
                inspect_fsis(path, {"mapping_reviewed": False})

    def test_csv_preserves_leading_zeros_and_rejects_wrong_width(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "official.csv"
            path.write_text("sample,program,date,result\n001,one,2025-01-01,P\n002,one,2025-01-02,N\n")
            before = sha256_file(path)
            result = inspect_fsis(path, self.contract)
            self.assertEqual(result["unique_populated_keys"], 2)
            self.assertEqual(before, sha256_file(path))
            path.write_text("sample,program,date,result\n001,one,2025-01-01,P,EXTRA\n")
            with self.assertRaises(ValueError):
                inspect_fsis(path, self.contract)

    def test_manual_and_downloaded_bytes_use_identical_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "official.json"
            path.write_text(json.dumps(self.rows))
            artifact = capture_artifact({"artifact_id": "fsis_data", "role": "source", "filename": path.name,
                                         "local_path": path.name}, root, "data/raw/fsis")
            self.assertEqual(inspect_fsis(path, self.contract), inspect_fsis(root / artifact["path"], self.contract))


class IngestionIntegrationTests(unittest.TestCase):
    def test_metadata_only_intake_confirms_source_without_claiming_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = {"identifier": "usda-fsis-105", "license": "https://creativecommons.org/publicdomain/zero/1.0/",
                       "distribution": [{"accessURL": "https://www.fsis.usda.gov/official"}]}
            metadata_path = root / "catalog.json"
            metadata_path.write_text(json.dumps(catalog))
            definition = {"artifacts": [{"artifact_id": "fsis_catalog_metadata", "role": "catalog",
                           "filename": metadata_path.name, "local_path": metadata_path.name}],
                          "directory": "data/raw/fsis", "intended_role": "biological", "license": "CC0",
                          "license_url": catalog["license"], "source_identifier": catalog["identifier"],
                          "resource_url": catalog["distribution"][0]["accessURL"]}
            config_path, contract_path = root / "sources.json", root / "contract.json"
            config_path.write_text(json.dumps({"datasets": {"fsis_raw_poultry": definition}}))
            contract_path.write_text('{"mapping_reviewed": false}')
            _, manifest = run_ingestion(root, config_path, contract_path, offline=True)
            fsis = manifest["datasets"]["fsis_raw_poultry"]
            self.assertEqual(fsis["source_status"], "official source confirmed, raw file not yet acquired")
            self.assertEqual(fsis["inspection"]["status"], "awaiting_official_file")
            self.assertIsNone(fsis["catalog_evidence"]["sample_field_descriptions"])
            self.assertEqual(fsis["catalog_evidence"]["data_dictionary_status"], "pending_official_sample_file_or_documentation")
            self.assertEqual(manifest["status"], "partial")

    def test_catalog_requires_matching_official_reference_and_preserves_field_evidence(self):
        from tracefront_data.ingest import inspect_fsis_catalog

        definition = {"source_identifier": "usda-fsis-105", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                      "resource_url": "https://www.fsis.usda.gov/official"}
        metadata = {"identifier": definition["source_identifier"], "license": definition["license_url"],
                    "distribution": [{"accessURL": definition["resource_url"]}], "fields": [{"name": "synthetic_field", "description": "test only"}]}
        evidence = inspect_fsis_catalog(metadata, definition)
        self.assertEqual(evidence["sample_field_descriptions"], {"fields": metadata["fields"]})
        self.assertFalse(evidence["catalog_dates_are_sample_release_dates"])
        with self.assertRaisesRegex(ValueError, "resource URL"):
            inspect_fsis_catalog({**metadata, "distribution": []}, definition)

    def test_reviewed_fixture_completes_only_with_exact_hash_and_dictionary(self):
        # Every byte in this temporary directory is a synthetic test fixture.
        import zipfile
        from tracefront_data.ingest import inspect_registered_fsis

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [{"sample": "001", "program": "one", "date": "2025-01-01", "result": "P"},
                    {"sample": "002", "program": "one", "date": "2025-01-02", "result": "N"}]
            source = root / "official.json"
            source.write_text(json.dumps({"data": rows, "dictionary": {"result": "P and N (synthetic fixture)"}}))
            metadata = root / "metadata.json"
            metadata.write_text(json.dumps({"identifier": "usda-fsis-105", "license": "https://creativecommons.org/publicdomain/zero/1.0/",
                                            "distribution": [{"accessURL": "https://www.fsis.usda.gov/official"}]}))
            context = root / "context.json"
            context.write_text('{"meta":{},"results":[{"recall_number":"R1","event_id":"E1"}]}')
            archive = root / "context.json.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.write(context, context.name)
            license_file = root / "license.html"
            license_file.write_text("synthetic license fixture")
            dictionary = root / "dictionary.pdf"
            dictionary.write_bytes(b"%PDF synthetic dictionary fixture")
            def local_spec(artifact_id, path):
                return {"artifact_id": artifact_id, "role": "synthetic_test_fixture", "filename": path.name, "local_path": path.name}
            config = {"datasets": {
                "fsis_raw_poultry": {"directory": "data/raw/fsis", "intended_role": "test", "license": "test",
                    "license_url": "https://creativecommons.org/publicdomain/zero/1.0/", "source_identifier": "usda-fsis-105",
                    "resource_url": "https://www.fsis.usda.gov/official", "artifacts": [local_spec("fsis_catalog_metadata", metadata)]},
                "openfda_enforcement": {"directory": "data/external/openfda", "intended_role": "context", "license": "test",
                    "license_url": "https://example.org/license", "source_release_version": "fixture",
                    "artifacts": [local_spec("openfda_local_json", context), local_spec("openfda_local_zip", archive),
                                  local_spec("openfda_license", license_file), local_spec("openfda_dictionary", dictionary)]},
            }}
            contract = {"mapping_reviewed": True, "reviewed_source_sha256": sha256_file(source),
                        "dictionary_release_match_verified": True, "records_pointer": "/data", "dictionary_pointer": "/dictionary",
                        "identity_columns": ["sample"], "fields": {"result": "result", "collection_date": "date"},
                        "cohort_filters": {"program": "one"}, "result_codes": {"positive": ["P"], "negative": ["N"]}}
            config_path, contract_path = root / "sources.json", root / "contract.json"
            config_path.write_text(json.dumps(config))
            contract_path.write_text(json.dumps(contract))
            _, manifest = run_ingestion(root, config_path, contract_path, fsis_file=source.name,
                                         fsis_source_version="synthetic-test-fixture", offline=True)
            self.assertEqual(manifest["status"], "complete")
            self.assertFalse(manifest["datasets"]["openfda_enforcement"]["inspection"]["training_eligible"])
            artifacts = manifest["datasets"]["fsis_raw_poultry"]["artifacts"]
            with self.assertRaisesRegex(ValueError, "exact source artifact"):
                inspect_registered_fsis(root, artifacts, {**contract, "reviewed_source_sha256": "0" * 64})

    def test_offline_manual_intake_reports_pending_without_assuming_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "official.json"
            source.write_text('[{"sample":"001","result":"Positive"}]')
            config = {"datasets": {"fsis_raw_poultry": {"artifacts": [], "directory": "data/raw/fsis",
                      "resource_url": "https://www.fsis.usda.gov/official", "intended_role": "biological", "license": "CC0", "license_url": "https://example.org/license"}}}
            config_path = root / "sources.json"
            contract_path = root / "contract.json"
            config_path.write_text(json.dumps(config))
            contract_path.write_text('{"mapping_reviewed": false}')
            path, manifest = run_ingestion(root, config_path, contract_path, fsis_file=source.name,
                                           fsis_source_version="synthetic-test-fixture", offline=True)
            self.assertEqual(manifest["status"], "partial")
            self.assertTrue(manifest["integrity"]["integrity_ok"])
            inspection = manifest["datasets"]["fsis_raw_poultry"]["inspection"]
            self.assertEqual(inspection["status"], "source_registered_review_pending")
            self.assertIsNone(inspection["profile"]["selected_rows"])
            self.assertTrue(path.is_file())
            with self.assertRaises(ValueError):
                run_ingestion(root, config_path, contract_path, fsis_file=source.name, offline=True)
            with self.assertRaises(ValueError):
                run_ingestion(root, config_path, contract_path, fsis_data_url="https://unverified.example/release.json", fsis_source_version="test")


if __name__ == "__main__":
    unittest.main()
