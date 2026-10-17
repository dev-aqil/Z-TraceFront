"""M5 PDP sample-context feature materialization tests; no models, labels or joins."""

import json
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tracefront_data.pdp_sample_context_features import (
    FEATURE_NULLABLE, assemble_row, compute_calendar, feature_names, load_assessment, materialize)

ROOT = Path(__file__).resolve().parents[1]


class CalendarTests(unittest.TestCase):
    def test_known_dates_map_deterministically(self):
        self.assertEqual(compute_calendar(date(2024, 1, 8)),
                         {"pdp_collection_dow_iso": 1, "pdp_collection_doy": 8, "pdp_collection_isoweek": 2})
        self.assertEqual(compute_calendar(date(2024, 1, 1))["pdp_collection_isoweek"], 1)
        self.assertEqual(compute_calendar(date(2024, 12, 31))["pdp_collection_isoweek"], 1)
        self.assertEqual(compute_calendar(date(2024, 12, 31))["pdp_collection_doy"], 366)

    def test_leap_day_maps_deterministically(self):
        self.assertEqual(compute_calendar(date(2024, 2, 29))["pdp_collection_doy"], 60)
        self.assertEqual(compute_calendar(date(2024, 2, 29))["pdp_collection_dow_iso"], 4)


class RowTests(unittest.TestCase):
    def make_sample(self):
        return {"source_row_number": 7, "sample_pk": "42", "commod": "AL", "commtype": "FR",
                "origin": "1", "country": None, "variety": "N/A", "claim": "NC",
                "quantity": None, "collection_date": date(2024, 1, 8)}

    def test_nulls_pass_through_unimputed_and_codes_survive_verbatim(self):
        row = assemble_row(self.make_sample())
        self.assertEqual(row["pdp_import_origin_country_code"], None)
        self.assertEqual(row["pdp_sample_unit_count"], None)
        self.assertEqual(row["pdp_commodity_code"], "AL")
        self.assertEqual(row["pdp_variety_text"], "N/A")
        self.assertEqual(row["pdp_collection_dow_iso"], 1)
        self.assertEqual(set(row), {"pdp_source_row_number", "pdp_sample_id", *feature_names()})

    def test_only_declared_nullable_features_may_be_null(self):
        sample = self.make_sample()
        sample["commod"] = None
        row = assemble_row(sample)
        with self.assertRaisesRegex(ValueError, "unexpected null in a non-null feature: pdp_commodity_code"):
            for name, value in row.items():
                if value is None and name not in FEATURE_NULLABLE:
                    raise ValueError("unexpected null in a non-null feature: " + name)

    def test_negative_sample_unit_count_is_rejected(self):
        sample = self.make_sample()
        sample["quantity"] = -1
        with self.assertRaisesRegex(ValueError, "negative sample-unit count"):
            assemble_row(sample)
        sample["quantity"] = None
        sample["collection_date"] = "2024-01-08"
        with self.assertRaisesRegex(ValueError, "collection_date must carry its declared date type"):
            assemble_row(sample)


def mock_assessment(product_columns, calendar_columns):
    def make_fields(entries):
        return [{"column": column, "table": "usda_pdp.samples" if use != "PRIOR_OUTCOME" else "usda_pdp.results",
                 "use": use, "canonical_name": "", "role": "CONTEXT", "unit_readiness": "CONFIRMED",
                 "field_availability": "M5_VERIFIED", "historical_availability": "M5_VERIFIED",
                 "predictor_approved": True, "leakage_class": "QUESTIONABLE"}
                for column, use in entries]
    return {"families": [
        {"id": "pdp_collection_calendar", "status": "REQUIRES_IMPLEMENTATION_REVIEW", "reason_codes": [],
         "field_assessments": make_fields(calendar_columns)},
        {"id": "pdp_product_context", "status": "REQUIRES_IMPLEMENTATION_REVIEW", "reason_codes": [],
         "field_assessments": make_fields(product_columns)}],
        "excluded_direct_focal_inputs": [{"table": "usda_pdp.results", "column": "mean"},
                                         {"table": "usda_pdp.results", "column": "concen"}]}


class GateTests(unittest.TestCase):
    def test_scope_must_cover_the_pinned_contract(self):
        with patch("tracefront_data.pdp_sample_context_features.sha256_file", return_value="changed"):
            with self.assertRaisesRegex(ValueError, "does not cover the pinned M4 contract"):
                load_assessment(ROOT)

    def test_unresolved_prerequisites_refuse_materialization(self):
        assessment = mock_assessment([("commod", "INPUT")], [("collection_date", "INPUT")])
        assessment["families"][0]["status"] = "BLOCKED"
        assessment["families"][0]["reason_codes"] = ["PREDICTION_TIME_AVAILABILITY_UNVERIFIED"]
        with patch("tracefront_data.pdp_sample_context_features.verify_m5_evidence"), \
             patch("tracefront_data.pdp_sample_context_features.verify_m4", return_value=({}, None)), \
             patch("tracefront_data.pdp_sample_context_features.assess_families", return_value=assessment):
            with self.assertRaisesRegex(ValueError, "prerequisites are unresolved"):
                load_assessment(ROOT)

    def test_unverified_field_availability_refuses_materialization_even_when_cleared(self):
        assessment = mock_assessment([("commod", "INPUT")], [("collection_date", "INPUT")])
        assessment["families"][0]["field_assessments"][0]["field_availability"] = "PENDING"
        with patch("tracefront_data.pdp_sample_context_features.verify_m5_evidence"), \
             patch("tracefront_data.pdp_sample_context_features.verify_m4", return_value=({}, None)), \
             patch("tracefront_data.pdp_sample_context_features.assess_families", return_value=assessment):
            with self.assertRaisesRegex(ValueError, "lacks M5-verified availability"):
                load_assessment(ROOT)

    def test_unapproved_predictor_refuses_materialization_even_when_cleared(self):
        assessment = mock_assessment([("commod", "INPUT")], [("collection_date", "INPUT")])
        assessment["families"][0]["field_assessments"][0]["predictor_approved"] = False
        with patch("tracefront_data.pdp_sample_context_features.verify_m5_evidence"), \
             patch("tracefront_data.pdp_sample_context_features.verify_m4", return_value=({}, None)), \
             patch("tracefront_data.pdp_sample_context_features.assess_families", return_value=assessment):
            with self.assertRaisesRegex(ValueError, "not an approved predictor"):
                load_assessment(ROOT)

    def test_outcome_guardrails_must_survive_in_the_assessment(self):
        assessment = mock_assessment([("commod", "INPUT")], [("collection_date", "INPUT")])
        assessment["excluded_direct_focal_inputs"] = [{"table": "usda_pdp.results", "column": "mean"}]
        with patch("tracefront_data.pdp_sample_context_features.verify_m5_evidence"), \
             patch("tracefront_data.pdp_sample_context_features.verify_m4", return_value=({}, None)), \
             patch("tracefront_data.pdp_sample_context_features.assess_families", return_value=assessment):
            with self.assertRaisesRegex(ValueError, "outcome exclusions are required guardrails"):
                load_assessment(ROOT)


class MaterializationTests(unittest.TestCase):
    """End-to-end run against pinned repo data; outputs and reports go to temp dirs."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory(dir=ROOT / "data/interim", prefix=".m5-test-out-")
        self.output = Path(self._temporary.name)
        self._reports = tempfile.TemporaryDirectory(dir=ROOT / "reports", prefix=".m5-test-reports-")
        self.reports = Path(self._reports.name)
        self.summary = self.reports / "m5_test_summary.json"
        self.report = self.reports / "m5_test_report.md"

    def tearDown(self):
        self._temporary.cleanup()
        self._reports.cleanup()

    def run_materialize(self, **kwargs):
        return materialize(ROOT, output_directory=self.output.relative_to(ROOT).as_posix(),
                           summary_path=self.summary.relative_to(ROOT).as_posix(),
                           report_path=self.report.relative_to(ROOT).as_posix(), **kwargs)

    def test_full_run_writes_pinned_unjoined_unlabeled_feature_table(self):
        result = self.run_materialize()
        self.assertEqual(result["rows"], 9872)
        self.assertEqual(result["features"], 10)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["null_counts"], {"pdp_import_origin_country_code": 6028,
                                                 "pdp_sample_unit_count": 2046})
        header = (self.output / "pdp_sample_context_features.csv").read_text(encoding="utf-8").splitlines()[0]
        expected = set(feature_names()) | {"pdp_source_row_number", "pdp_sample_id"}
        for column in header.split(","):
            self.assertIn(column, expected)
            for marker in ("label", "contam", "result_code", "concentration", "recall", "inspection",
                           "risk", "target", "censor"):
                self.assertNotIn(marker, column.lower())
        schema = json.loads((self.output / "pdp_sample_context_features.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["status"], "NOT MODEL-READY")
        self.assertEqual(schema["prediction_context"]["prediction_cutoff"], "2025-12-23")
        self.assertIn("cross-source joins", schema["not_performed"])
        # The feature table must not contain any analytical-outcome column name.
        self.assertTrue({"pdp_residue_concentration", "pdp_result_code"}.isdisjoint(expected))
        # A second run re-verifies the identical pinned outputs instead of rewriting.
        second = self.run_materialize()
        self.assertEqual(second["rows"], 9872)

    def test_readback_detects_tampered_feature_bytes(self):
        self.run_materialize()
        path = self.output / "pdp_sample_context_features.csv"
        path.write_text(path.read_text(encoding="utf-8") + "999,not-a-sample\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differ from their pinned summary"):
            self.run_materialize()

    def test_readback_rejects_nulls_undeclared_in_the_pinned_missingness(self):
        self.run_materialize()
        summary = json.loads(self.summary.read_text(encoding="utf-8"))
        self.assertEqual(summary["feature_null_counts"], {"pdp_import_origin_country_code": 6028,
                                                          "pdp_sample_unit_count": 2046})
        with self.subTest("exact null passthrough equals the pinned M2 missingness"):
            summary_hold = self.summary.read_text(encoding="utf-8")
            tampered = json.loads(summary_hold)
            tampered["artifacts"]["outputs"]["pdp_sample_context_features.csv"]["sha256"] = "0" * 64
            self.summary.write_text(json.dumps(tampered))
            with self.assertRaisesRegex(ValueError, "differ from their pinned summary"):
                self.run_materialize()
            self.summary.write_text(summary_hold)


if __name__ == "__main__":
    unittest.main()
