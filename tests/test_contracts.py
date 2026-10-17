"""M4 metadata contract tests; no table transformations or training fixtures."""

import copy
import csv
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tracefront_data.contracts import load_verified_inputs, render_dictionary, validate_contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "configs/source_contracts.json").read_text())
M3 = json.loads((ROOT / "reports/m3_eda_summary.json").read_text())
# Tests remain runnable without raw/interim artifacts on a clean clone.
SCHEMAS = {key:{"source":table["source"], "columns":{
    name:{"datatype":field["datatype"], "nullable":field["nullable"]} for name,field in table["fields"].items()},
    "row_granularity":table["row_granularity"], "null_encoding":table["null_encoding"]}
    for key,table in CONTRACT["tables"].items()}
PROFILES = {key:M3["sources"][table["source_entry"]]["tables"][table["source_table"]]
            for key,table in CONTRACT["tables"].items()}


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(CONTRACT)

    def check(self):
        return validate_contract(self.contract, SCHEMAS, PROFILES)

    def test_full_source_coverage_and_no_materialization(self):
        result = self.check()
        self.assertEqual(result["source_tables"], 7)
        self.assertEqual(result["mapped_fields"], 106)
        self.assertEqual(result["approved_predictors"], 0)
        self.assertEqual(result["data_tables_written"], 0)
        self.assertEqual(result["labels_created"], 0)

    def test_missing_column_and_unacquired_table_rejected(self):
        self.contract["tables"]["usda_pdp.samples"]["fields"].pop("sample_pk")
        with self.assertRaisesRegex(ValueError, "field mapping"):
            self.check()
        self.contract = copy.deepcopy(CONTRACT)
        self.contract["tables"]["fsis.fake"] = {}
        with self.assertRaisesRegex(ValueError, "cohort"):
            self.check()

    def test_decimal_coercion_and_nullability_change_rejected(self):
        field = self.contract["tables"]["usda_pdp.results"]["fields"]["concen"]
        field["datatype"] = "float64"
        with self.assertRaisesRegex(ValueError, "datatypes"):
            self.check()
        field["datatype"] = "decimal"
        field["nullable"] = False
        with self.assertRaisesRegex(ValueError, "nullability"):
            self.check()

    def test_no_implicit_approval_of_predictors_labels_or_joins(self):
        for key in ["mapping_execution_enabled", "label_materialization_enabled", "cross_source_joins_enabled"]:
            with self.subTest(key=key):
                self.contract = copy.deepcopy(CONTRACT)
                self.contract["policy"][key] = True
                with self.assertRaises(ValueError):
                    self.check()
        self.contract = copy.deepcopy(CONTRACT)
        self.contract["tables"]["usda_pdp.results"]["fields"]["concen"]["predictor_approved"] = True
        with self.assertRaises(ValueError):
            self.check()

    def test_pending_units_cannot_be_promoted(self):
        field = self.contract["tables"]["opendosm_crops_state.crops_state"]["fields"]["production"]
        self.assertIsNone(field["unit"]["canonical"])
        field["unit"]["canonical"] = "tonnes"
        with self.assertRaisesRegex(ValueError, "Pending physical units"):
            self.check()
        field["unit"]["status"] = "VERIFIED"
        with self.assertRaisesRegex(ValueError, "production units"):
            self.check()

    def test_reference_dates_do_not_establish_historical_availability(self):
        table = self.contract["tables"]["opendosm_crops_district_area.crops_district_area"]
        table["history_availability"]["available_at"] = "2017-01-01"
        with self.assertRaisesRegex(ValueError, "Historical availability"):
            self.check()

    def test_pdp_identity_and_code_semantics_are_protected(self):
        for table, column, alias in [("samples", "source_id", "supplier_id"), ("results", "lab", "factory_id")]:
            with self.subTest(column=column):
                self.contract = copy.deepcopy(CONTRACT)
                self.contract["tables"]["usda_pdp."+table]["fields"][column]["canonical_name"] = alias
                with self.assertRaises(ValueError):
                    self.check()
        self.contract = copy.deepcopy(CONTRACT)
        self.contract["tables"]["usda_pdp.results"]["fields"]["mean"]["allowed_values"]["documented_code_meanings"].pop("NP")
        with self.assertRaisesRegex(ValueError, "result-code distinctions"):
            self.check()

    def test_outcomes_and_retrospective_fields_cannot_be_safe(self):
        for key,column in [("usda_pdp.results","concen"),("openfda_enforcement.recalls","status")]:
            self.contract = copy.deepcopy(CONTRACT)
            self.contract["tables"][key]["fields"][column]["leakage_class"] = "SAFE"
            with self.assertRaises(ValueError):
                self.check()

    def test_noaa_measurement_not_a_batch_feature(self):
        table = self.contract["tables"]["noaa_ghcn_daily.daily_observations"]
        table["fields"]["value"]["canonical_name"] = "transport_max_temp_c"
        with self.assertRaisesRegex(ValueError, "Station weather"):
            self.check()

    def test_keys_and_source_paths_must_be_valid(self):
        table = self.contract["tables"]["usda_pdp.samples"]
        table["primary_key"] = ["nonexistent"]
        with self.assertRaisesRegex(ValueError, "Primary key"):
            self.check()
        table["data_path"] = "data/raw/not-a-clean-table.csv"
        with self.assertRaisesRegex(ValueError, "paths"):
            self.check()

    def test_future_categories_and_pending_source_fields_not_invented(self):
        field = self.contract["tables"]["usda_pdp.samples"]["fields"]["commod"]
        field["allowed_values"]["observed_values_are_exhaustive_for_future_releases"] = True
        with self.assertRaisesRegex(ValueError, "future-release"):
            self.check()
        self.contract = copy.deepcopy(CONTRACT)
        self.contract["pending_sources"]["fsis_raw_poultry"]["mappings"]["guessed_sample_id"] = "id"
        with self.assertRaisesRegex(ValueError, "fabricated"):
            self.check()

    def test_dictionary_renders_every_field_deterministically(self):
        before = copy.deepcopy(self.contract)
        first = render_dictionary(self.contract)
        self.assertEqual(first, render_dictionary(self.contract))
        rows = list(csv.DictReader(io.StringIO(first[1])))
        self.assertEqual(len(rows), 106)
        self.assertTrue(all(row["predictor_approved"] == "False" for row in rows))
        self.assertEqual(self.contract, before)
        suffix = next(row for row in rows if row["m2_column"]=="source_id")
        self.assertIn('""', suffix["allowed_values"])

    def test_changed_upstream_hash_fails_before_reading_data(self):
        with patch("tracefront_data.contracts.sha256_file", return_value="mismatch"):
            with self.assertRaisesRegex(ValueError, "M3 report changed"):
                load_verified_inputs(ROOT)


if __name__ == "__main__":
    unittest.main()
