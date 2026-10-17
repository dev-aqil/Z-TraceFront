"""M2 semantic/integrity regressions. All fixtures are synthetic."""

import copy
import csv
from datetime import date
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tracefront_data.audit import sha256_file
from tracefront_data.clean import run_cleaning, verify_cleaned
from tracefront_data.cleaning.common import number, parse_date, read_table, text
from tracefront_data.cleaning.context import clean_openfda, clean_opendosm
from tracefront_data.cleaning.pdp import clean_pdp
from tracefront_data.cleaning.weather import clean_noaa

ROOT = Path(__file__).parents[1]
M1 = json.loads((ROOT / "reports/m1_source_manifest.json").read_text())
CUTOFF = date(2026, 10, 17)


class CleaningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / "clean"

    def pdp(self, samples, results):
        schema = copy.deepcopy(M1["datasets"]["usda_pdp"]["inspection"]["dictionary_mapping"])
        path = self.root / "synthetic.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for kind, records in [("sample", samples), ("result", results)]:
                stream = io.StringIO(newline="")
                writer = csv.writer(stream, delimiter="|", lineterminator="\n")
                for raw in records:
                    writer.writerow(raw.get(n, "") for n in schema[kind + "_columns"])
                archive.writestr(schema[kind + "_member"], stream.getvalue())
        schema["reviewed_archive_sha256"] = sha256_file(path)
        return path, schema

    @staticmethod
    def sample(**overrides):
        return {"SAMPLE_PK": "001", "STATE": "CA", "YEAR": "24", "MONTH": "02", "DAY": "29", "SITE": "0007",
                "COMMOD": "XX", "SOURCE_ID": " ", "ORIGIN": "1", "VARIETY": "N/A", **overrides}

    @staticmethod
    def result(**overrides):
        return {"SAMPLE_PK": "001", "COMMOD": "XX", "COMMTYPE": "FR", "LAB": "XX1", "PESTCODE": "001",
                "MEAN": "ND", "LOD": "0.01", "CONUNIT": "M", **overrides}

    def test_decimal_missingness_and_nonfinite_rejection(self):
        self.assertEqual(number(" 1.250 "), "1.250")
        self.assertIsNone(number(" "))
        self.assertEqual(text(" N/A "), "N/A")
        for value in ["NaN", "Infinity", "-1", "invalid"]:
            with self.assertRaises(ValueError):
                number(value, minimum="0")
        with self.assertRaises(ValueError):
            number("1.5", integer=True)

    def test_date_validation_is_strict_and_uses_frozen_cutoff(self):
        self.assertEqual(parse_date("20240229", "%Y%m%d", CUTOFF), "2024-02-29")
        for value in ["02121207", "20230229", "2024-01-01", "20270101", "2024011"]:
            with self.assertRaises(ValueError):
                parse_date(value, "%Y%m%d", CUTOFF)

    def test_pdp_preserves_ids_censoring_and_analytical_duplicates(self):
        records = [self.result(), self.result(MEAN="NP"), self.result(MEAN="O", CONCEN="0.20"), self.result(),
                   self.result(SAMPLE_PK="999"), self.result(CONCEN="-0.1"), self.result(MEAN="UNKNOWN")]
        path, schema = self.pdp([self.sample()], records)
        before = path.read_bytes()
        stats = clean_pdp(path, self.out, schema, CUTOFF, {}, self.root)
        sample = list(read_table(self.out / "samples.csv"))[0]
        self.assertEqual(sample["sample_pk"], "001")
        self.assertEqual(sample["site"], "0007")
        self.assertEqual(sample["collection_date"], date(2024, 2, 29))
        self.assertEqual(sample["source_id"], "")
        self.assertEqual(sample["country_missing_reason"], "not_applicable_domestic")
        self.assertEqual(sample["variety"], "N/A")
        rows = list(read_table(self.out / "results.csv"))
        self.assertEqual([r["mean"] for r in rows], ["ND", "NP", "O", "ND"])
        self.assertEqual(rows[0]["concen_raw"], "")
        self.assertIsNone(rows[0]["concen"])
        self.assertEqual(rows[0]["concen_missing_reason"], "censored_ND")
        self.assertEqual(rows[1]["concen_missing_reason"], "censored_NP")
        self.assertEqual(rows[2]["concen"], Decimal("0.20"))
        self.assertEqual(rows[3]["duplicate_of_source_row"], 1)
        self.assertEqual(stats["tables"]["results"]["rejected_rows"], 3)
        self.assertEqual(stats["tables"]["results"]["duplicate_rows"], 1)
        self.assertNotIn("pesticide_exceedance", rows[0])
        self.assertEqual(path.read_bytes(), before)

    def test_conflicting_pdp_samples_quarantine_all_versions_and_their_results(self):
        path, schema = self.pdp([self.sample(), self.sample(ORIGIN="2")], [self.result()])
        stats = clean_pdp(path, self.out, schema, CUTOFF, {}, self.root)
        self.assertEqual(stats["tables"]["samples"]["rejected_rows"], 2)
        self.assertEqual(stats["tables"]["results"]["rejected_rows"], 1)
        self.assertEqual(list(read_table(self.out / "results.csv")), [])

    def test_bad_pdp_date_and_quantity_have_rejection_evidence(self):
        path, schema = self.pdp([self.sample(DAY="30", QUANTITY="-2")], [])
        stats = clean_pdp(path, self.out, schema, CUTOFF, {}, self.root)
        self.assertEqual(stats["tables"]["samples"]["invalid_date_rows"], 1)
        self.assertEqual(stats["tables"]["samples"]["invalid_numeric_rows"], 1)
        evidence = json.loads((self.out / "samples.rejected.jsonl").read_text())
        self.assertEqual(evidence["raw_values"]["DAY"], "30")

    @staticmethod
    def monthly(element="TMAX", slots=None):
        values = ["-9999   "] * 31
        for day, value in (slots or {}).items():
            values[day - 1] = value
        return "MYM00048647" + "202402" + element + "".join(values)

    def test_noaa_flags_units_missingness_and_leap_calendar(self):
        path = self.root / "fixture.dly"
        path.write_text(self.monthly(slots={1: "  302HKa", 2: "  -50   "}) + "\n")
        stats = clean_noaa(path, self.out, CUTOFF, {})
        rows = list(read_table(self.out / "daily_observations.csv"))
        self.assertEqual(len(rows), 29)
        self.assertEqual(rows[0]["value"], Decimal("30.2"))
        self.assertEqual(rows[0]["unit"], "degC")
        self.assertEqual([rows[0][k] for k in ["measurement_flag", "quality_flag", "source_flag"]], ["H", "K", "a"])
        self.assertEqual(rows[0]["observation_status"], "quality_flagged")
        self.assertEqual(rows[1]["value"], Decimal("-5"))
        self.assertIsNone(rows[2]["value"])
        self.assertEqual(rows[2]["raw_value"], -9999)
        self.assertEqual(rows[2]["quality_flag"], " ")
        self.assertEqual(stats["excluded_noncalendar_padding_slots"], 2)

    def test_noaa_negative_rainfall_is_rejected_trace_and_sentinel_remain(self):
        path = self.root / "fixture.dly"
        path.write_text(self.monthly("PRCP", {1: "   -1   ", 2: "    0T S"}) + "\n")
        stats = clean_noaa(path, self.out, CUTOFF, {})
        rows = list(read_table(self.out / "daily_observations.csv"))
        self.assertEqual(stats["tables"]["daily_observations"]["rejected_rows"], 1)
        self.assertEqual(rows[0]["value"], Decimal("0"))
        self.assertEqual(rows[0]["measurement_flag"], "T")
        self.assertIsNone(rows[1]["value"])

    def test_noaa_noncalendar_data_is_not_silently_dropped(self):
        path = self.root / "fixture.dly"
        path.write_text(self.monthly(slots={30: "   10   "}) + "\n")
        stats = clean_noaa(path, self.out, CUTOFF, {})
        self.assertEqual(stats["monthly_input_accounting"]["rejected_rows"], 1)
        evidence = json.loads((self.out / "monthly_records.rejected.jsonl").read_text())
        self.assertIn("noncalendar_padding_contains_data_or_flags", evidence["reason_codes"])

    def dosm(self, rows):
        columns = ["state", "date", "crop_type", "planted_area", "production"]
        path = self.root / "crops.csv"
        with path.open("w", newline="") as stream:
            writer = csv.writer(stream); writer.writerow(columns); writer.writerows(rows)
        return path, columns

    def test_opendosm_reference_semantics_null_zero_and_duplicates(self):
        row = [" Johor ", "2017-01-01", "cash_crops", "0", ""]
        path, columns = self.dosm([row, row, ["Kedah", "2017-01-01", "cash_crops", "-1", "1"],
                                  ["Perlis", "2017-02-01", "cash_crops", "1", "1"]])
        stats = clean_opendosm(path, self.out, "crops_state", columns, CUTOFF, {})
        rows = list(read_table(self.out / "crops_state.csv"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["state"], "Johor")
        self.assertEqual(rows[0]["reference_year"], 2017)
        self.assertEqual(rows[0]["reference_date"], date(2017, 1, 1))
        self.assertEqual(rows[0]["planted_area"], Decimal(0))
        self.assertIsNone(rows[0]["production"])
        self.assertNotIn("observation_date", rows[0])
        self.assertNotIn("publication_date", rows[0])
        self.assertEqual(stats["tables"]["crops_state"]["rejected_rows"], 3)

    def test_opendosm_conflicting_keys_and_malformed_widths_have_evidence(self):
        path, columns = self.dosm([["Johor", "2017-01-01", "cash_crops", "1", "2"],
                                  ["Johor", "2017-01-01", "cash_crops", "1", "3"],
                                  ["Kedah", "2017-01-01", "cash_crops", "1", "2", "extra"]])
        stats = clean_opendosm(path, self.out, "crops_state", columns, CUTOFF, {})
        self.assertEqual(stats["tables"]["crops_state"]["rejected_rows"], 3)
        self.assertEqual(stats["tables"]["crops_state"]["malformed_rows"], 1)
        self.assertEqual(len((self.out / "crops_state.rejected.jsonl").read_text().splitlines()), 3)

    def test_openfda_dates_shared_events_and_context_only(self):
        columns = M1["datasets"]["openfda_enforcement"]["inspection"]["columns"]
        def recall(number, **updates):
            return {"recall_number": number, "event_id": "shared", "report_date": "20240101", "openfda": {},
                    "recall_initiation_date": "02121207", "recalling_firm": " Test firm ", "classification": "class i", **updates}
        first = recall("F-001")
        path = self.root / "recalls.json"
        path.write_text(json.dumps({"results": [first, recall("F-002"), first, recall(""), recall("F-003", report_date="20240230")]}))
        stats = clean_openfda(path, self.out, columns, CUTOFF, {})
        rows = list(read_table(self.out / "recalls.csv"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["classification"], "Class I")
        self.assertEqual(rows[0]["recalling_firm"], "Test firm")
        self.assertIsNone(rows[0]["recall_initiation_date"])
        self.assertEqual(rows[0]["recall_initiation_date_raw"], "02121207")
        self.assertEqual(rows[0]["openfda"], {})
        self.assertEqual(rows[0]["report_date"], date(2024, 1, 1))
        for key in ["contaminated", "contamination_label", "supplier_risk", "pathogen_positive"]:
            self.assertNotIn(key, rows[0])
        self.assertEqual(stats["tables"]["recalls"]["rejected_rows"], 3)
        self.assertFalse(stats["contamination_label_created"])

    def baseline(self):
        path, columns = self.dosm([[r"\N", "2017-01-01", "cash_crops", "0", "2"]])
        raw = self.root / "data/raw/fixture.csv"
        raw.parent.mkdir(parents=True)
        raw.write_bytes(path.read_bytes())
        artifact = {"artifact_id": "crops_state", "role": "data", "status": "captured", "path": "data/raw/fixture.csv",
                    "size_bytes": raw.stat().st_size, "sha256": sha256_file(raw)}
        source = {"m2_eligible": True, "artifacts": [artifact], "publisher": "synthetic fixture", "license": "fixture only",
                  "canonical_source_url": "https://example.gov/synthetic", "intended_ml_role": "EXTERNAL_CONTEXT_SOURCE",
                  "contamination_domain": "CONTEXT_ONLY", "inspection": {"columns": columns, "rows": 1}}
        datasets = {"opendosm_crops_state": source, "fsis_raw_poultry": {"m2_eligible": False, "artifacts": []},
                    "fda_inspections": {"m2_eligible": False, "artifacts": []}}
        receipt = self.root / "receipt.json"
        receipt.write_text(json.dumps({"datasets": datasets, "status": "partial"}))
        manifest = self.root / "sources.json"
        manifest.write_text(json.dumps({"datasets": datasets, "receipt": receipt.name,
                                       "receipt_sha256": sha256_file(receipt), "receipt_created_at": "2026-10-17T00:00:00Z"}))
        return manifest, raw

    def test_pipeline_determinism_raw_immutability_eligibility_and_null_escape(self):
        manifest, raw = self.baseline()
        before = raw.read_bytes()
        first = run_cleaning(self.root, manifest, Path("data/interim/first"))
        second = run_cleaning(self.root, manifest, Path("data/interim/second"))
        self.assertEqual(first["outputs"], second["outputs"])
        self.assertEqual(raw.read_bytes(), before)
        self.assertEqual(first["skipped_ineligible_sources"], ["fda_inspections", "fsis_raw_poultry"])
        self.assertEqual(set(first["sources"]), {"opendosm_crops_state"})
        table = self.root / "data/interim/first/opendosm_crops_state/crops_state.csv"
        self.assertEqual(list(read_table(table))[0]["state"], r"\N")
        self.assertEqual(run_cleaning(self.root, manifest, Path("data/interim/first"))["outputs"], first["outputs"])
        table.write_text("existing output changed")
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            run_cleaning(self.root, manifest, Path("data/interim/first"))
        self.assertEqual(table.read_text(), "existing output changed")

    def test_corrupt_baseline_stops_before_output_creation(self):
        manifest, raw = self.baseline()
        raw.write_text("tampered")
        with self.assertRaisesRegex(ValueError, "integrity failed"):
            run_cleaning(self.root, manifest, Path("data/interim/first"))
        self.assertFalse((self.root / "data/interim/first").exists())

    def test_orchestrator_uses_actual_m1_count_fields_for_all_six_eligible_entries(self):
        """Exercise every adapter with tiny synthetic bytes and M1-shaped metadata."""
        pdp_path, schema = self.pdp([self.sample()], [self.result()])
        weather = self.root / "fixture.dly"
        weather.write_text(self.monthly() + "\n")
        recall = self.root / "fixture.json"
        recall.write_text(json.dumps({"results": [{"recall_number": "F-SYNTH", "report_date": "20240101", "openfda": {}}]}))
        datasets = {}
        for name in sorted(k for k, s in M1["datasets"].items() if s["m2_eligible"]):
            source = copy.deepcopy(M1["datasets"][name])
            source["publisher"] = "synthetic fixture"
            source["license"] = "synthetic fixture only"
            if name == "usda_pdp":
                path, artifact_id = pdp_path, "pdp_2024"
                source["inspection"] = {"dictionary_mapping": schema, "sample_table": {"rows": 1}, "result_table": {"rows": 1}}
            elif name == "noaa_ghcn_daily":
                path, artifact_id = weather, "ghcn_station_data"
                source["inspection"] = {"rows": 1}
            elif name == "openfda_enforcement":
                path, artifact_id = recall, "openfda_local_json"
                source["inspection"] = {"rows": 1, "columns": source["inspection"]["columns"]}
            else:
                artifact_id = name.removeprefix("opendosm_")
                path = self.root / (artifact_id + ".csv")
                columns = source["inspection"]["columns"]
                raw = {"state": "Johor", "district": "synthetic_district", "crop_type": "cash_crops",
                       "crop_species": "synthetic_species", "date": "2017-01-01", "production": "2", "planted_area": "1"}
                with path.open("w", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=columns)
                    writer.writeheader(); writer.writerow({k: raw[k] for k in columns})
                source["inspection"] = {"rows": 1, "columns": columns}
            source["artifacts"] = [{"artifact_id": artifact_id, "role": "data", "status": "captured",
                                    "path": path.relative_to(self.root).as_posix(), "size_bytes": path.stat().st_size,
                                    "sha256": sha256_file(path)}]
            datasets[name] = source
        receipt = self.root / "all-receipt.json"
        receipt.write_text(json.dumps({"datasets": datasets, "status": "partial"}))
        manifest = self.root / "all-sources.json"
        manifest.write_text(json.dumps({"datasets": datasets, "receipt": receipt.name, "receipt_sha256": sha256_file(receipt),
                                       "receipt_created_at": "2026-10-17T00:00:00Z"}))
        result = run_cleaning(self.root, manifest, Path("data/interim/all"))
        self.assertEqual(len(result["sources"]), 6)
        self.assertEqual(result["sources"]["openfda_enforcement"]["tables"]["recalls"]["raw_rows"], 1)
        self.assertEqual(result["sources"]["usda_pdp"]["tables"]["results"]["clean_rows"], 1)
        checked = verify_cleaned(self.root, result)
        self.assertTrue(checked["integrity_ok"])
        self.assertEqual(checked["typed_tables_read"], 7)

    def test_raw_layer_output_is_rejected(self):
        manifest, _ = self.baseline()
        with self.assertRaisesRegex(ValueError, "never the raw layer"):
            run_cleaning(self.root, manifest, Path("data/raw/illegal"))


if __name__ == "__main__":
    unittest.main()
