"""M5 readiness evidence and exclusion tests; no models or feature fixtures."""

import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tracefront_data.feature_readiness import assess_families, render_report, unit_readiness, verify_m4

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "configs/source_contracts.json").read_text())
SCOPE = json.loads((ROOT / "configs/m5_feature_scope.json").read_text())


class FeatureReadinessTests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(CONTRACT)
        self.scope = copy.deepcopy(SCOPE)

    def family(self, name):
        result = assess_families(self.contract, self.scope)
        return next(f for f in result["families"] if f["id"] == name)

    def test_experiment_only_clears_the_two_passing_pdp_families(self):
        original = copy.deepcopy(self.contract)
        result = assess_families(self.contract, self.scope)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["assessment_status"], "COMPLETE")
        self.assertEqual(result["family_status_counts"], {"BLOCKED": 9,
                                                          "REQUIRES_IMPLEMENTATION_REVIEW": 2})
        for name in ["features_emitted", "feature_tables_written", "labels_created", "joins_performed"]:
            self.assertEqual(result[name], 0)
        self.assertEqual(self.contract, original)
        cleared = sorted(f["id"] for f in result["families"] if f["status"] != "BLOCKED")
        self.assertEqual(cleared, ["pdp_collection_calendar", "pdp_product_context"])
        for family in result["families"]:
            if family["status"] == "BLOCKED":
                self.assertIn("PREDICTION_TIME_AVAILABILITY_UNVERIFIED", family["reason_codes"])

    def test_cleared_fields_are_m5_verified_and_outcomes_stay_excluded(self):
        result = assess_families(self.contract, self.scope)
        family = next(f for f in result["families"] if f["id"] == "pdp_product_context")
        for field in family["field_assessments"]:
            self.assertEqual(field["field_availability"], "M5_VERIFIED")
            self.assertEqual(field["historical_availability"], "M5_VERIFIED")
            self.assertTrue(field["predictor_approved"])
            self.assertNotIn("FOCAL_OUTCOME_INPUT_EXCLUDED", family["reason_codes"])
        results_family = next(f for f in result["families"] if f["id"] == "supplier_facility_test_history")
        self.assertEqual(results_family["status"], "BLOCKED")
        self.assertIn(("usda_pdp.results", "concen"), {(f["table"], f["column"])
                                                      for f in result["excluded_direct_focal_inputs"]})

    def test_weather_units_are_confirmed_without_claiming_availability(self):
        result = self.family("weather_environment")
        value = next(f for f in result["field_assessments"] if f["column"]=="value")
        self.assertEqual(value["unit_readiness"], "CONFIRMED_SOURCE_CODED")
        self.assertNotIn("UNIT_VERIFICATION_PENDING", result["reason_codes"])
        self.assertIn("PREDICTION_TIME_AVAILABILITY_UNVERIFIED", result["reason_codes"])
        self.assertIn("WEATHER_QA_COVERAGE_POLICY_UNDEFINED", result["reason_codes"])
        table = self.contract["tables"]["noaa_ghcn_daily.daily_observations"]
        field = copy.deepcopy(table["fields"]["value"])
        field["unit"]["element_units"] = {}
        self.assertEqual(unit_readiness(field, table), "PENDING")

    def test_agricultural_area_and_production_have_different_unit_evidence(self):
        area = self.family("agricultural_area_context")
        production = self.family("agricultural_production_context")
        self.assertNotIn("UNIT_VERIFICATION_PENDING", area["reason_codes"])
        self.assertIn("UNIT_VERIFICATION_PENDING", production["reason_codes"])
        self.assertEqual(production["status"], "BLOCKED")
        self.assertIn("AGRICULTURAL_RELEASE_AVAILABILITY_ABSENT", area["reason_codes"])

    def test_declaring_cutoff_does_not_prove_source_availability(self):
        # Cutoff/precision are declared, but the M5 field-level evidence overlay is
        # removed: an unverified availability statement alone must not clear anything.
        self.scope["m5_evidence"] = {}
        self.scope["m5_verified_tables"] = []
        self.scope["m5_verified_inputs"] = []
        self.scope["decision_contract"] = {
            "experiment_definition": "pdp_2024_sample_context_retrospective",
            "prediction_cutoff": "2025-12-23", "prediction_cutoff_precision": "DATE",
            "applies_to_families": self.scope["decision_contract"]["applies_to_families"],
            "availability_evidence": "unverified statement"}
        result = self.family("pdp_product_context")
        self.assertNotIn("PREDICTION_CUTOFF_UNDEFINED", result["reason_codes"])
        self.assertIn("PREDICTION_TIME_AVAILABILITY_UNVERIFIED", result["reason_codes"])
        self.assertIn("PREDICTOR_APPROVAL_PENDING", result["reason_codes"])
        self.assertEqual(result["status"], "BLOCKED")

    def test_documented_cutoff_and_evidence_clear_field_scoped_availability(self):
        result = self.family("pdp_product_context")
        self.assertNotIn("PREDICTION_TIME_AVAILABILITY_UNVERIFIED", result["reason_codes"])
        self.assertNotIn("PREDICTION_CUTOFF_UNDEFINED", result["reason_codes"])
        self.assertEqual(result["status"], "REQUIRES_IMPLEMENTATION_REVIEW")
        result = self.family("pdp_collection_calendar")
        self.assertEqual(result["status"], "REQUIRES_IMPLEMENTATION_REVIEW")

    def test_outcome_missingness_cannot_become_a_focal_predictor(self):
        family = next(f for f in self.scope["families"] if f["id"]=="pdp_input_missingness")
        family["references"].append({"table":"usda_pdp.results", "column":"concen_missing_reason", "use":"INPUT"})
        result = self.family("pdp_input_missingness")
        self.assertIn("FOCAL_OUTCOME_INPUT_EXCLUDED", result["reason_codes"])
        all_results = assess_families(self.contract, self.scope)
        excluded = {(f["table"],f["column"]) for f in all_results["excluded_direct_focal_inputs"]}
        self.assertEqual(len(excluded), 20)
        self.assertIn(("usda_pdp.results","mean"), excluded)
        self.assertIn(("openfda_enforcement.recalls","classification"), excluded)

    def test_real_sensor_and_inspection_absence_stays_explicit(self):
        cold = self.family("cold_chain_temperature")
        self.assertEqual(cold["field_assessments"], [])
        self.assertIn("BATCH_SENSOR_SERIES_ABSENT", cold["reason_codes"])
        inspections = self.family("inspection_history")
        self.assertIn("SOURCE_NOT_ACQUIRED", inspections["reason_codes"])
        history = self.family("supplier_facility_test_history")
        self.assertIn("VERIFIED_SUPPLIER_FACILITY_ID_ABSENT", history["reason_codes"])

    def test_fabricated_references_and_materialization_rejected(self):
        self.scope["families"][0]["references"][0]["column"] = "fabricated_supplier_id"
        with self.assertRaisesRegex(ValueError, "fabricated"):
            assess_families(self.contract, self.scope)
        self.scope = copy.deepcopy(SCOPE)
        self.scope["materialize_features"] = True
        with self.assertRaisesRegex(ValueError, "cannot authorize"):
            assess_families(self.contract, self.scope)
        self.scope = copy.deepcopy(SCOPE)
        self.scope["families"][3]["id"] = self.scope["families"][8]["id"]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            assess_families(self.contract, self.scope)

    def test_m4_hash_mismatch_fails_before_source_verification(self):
        with patch("tracefront_data.feature_readiness.sha256_file", return_value="changed"), patch("tracefront_data.feature_readiness.load_verified_inputs") as downstream:
            with self.assertRaisesRegex(ValueError, "M4 artifact changed"):
                verify_m4(ROOT)
            downstream.assert_not_called()

    def test_repeated_assessment_and_render_are_identical(self):
        first = assess_families(self.contract, self.scope)
        second = assess_families(self.contract, self.scope)
        self.assertEqual(first, second)
        self.assertEqual(render_report(first), render_report(second))
        self.assertIn("Milestone PARTIAL", render_report(first))
        self.assertIn("separate materialization module", render_report(first))
        self.assertIn("NOT MODEL-READY", render_report(first))


if __name__ == "__main__":
    unittest.main()
