"""M3 regression proofs: descriptive counts, denominators and immutable inputs."""

from collections import Counter
import copy
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tracefront_data.eda import (Numeric, inspect_rejections, inspect_openfda_presence,
                                 noaa_flag_documentation, profile_table, verify_inputs, write_reports)


def schema(**columns):
    return {"row_granularity": "synthetic", "columns": {k:{"datatype":v} for k,v in columns.items()}}


class EdaTests(unittest.TestCase):
    def test_null_blank_zero_and_literal_na_are_distinct(self):
        rows = [{"category": None, "amount": None}, {"category": "", "amount": Decimal(0)},
                {"category": "N/A", "amount": Decimal(1)}, {"category": " ", "amount": Decimal(2)}]
        original = copy.deepcopy(rows)
        p = profile_table(rows, schema(category="string", amount="decimal"), "fixture", "fixture")
        self.assertEqual(p["null_counts"], {"category":1, "amount":1})
        self.assertEqual(p["empty_string_counts"], {"category":1})
        self.assertEqual(p["literal_ambiguous_missing_tokens"], {"category":1})
        self.assertEqual(p["categories"]["category"]["all_counts"], {"<EMPTY>":1, "<BLANK>":1, "N/A":1})
        self.assertEqual(p["numeric"]["amount [unspecified]"]["zero_count"], 1)
        self.assertEqual(rows, original)

    def test_numeric_exact_quantiles_histogram_and_empty(self):
        p = Numeric()
        for value in [0, 0, 1, 10]:
            p.add(value)
        result = p.finish()
        self.assertEqual(result["quantiles"]["p50"], "0")
        self.assertEqual(result["quantiles"]["p95"], "10")
        self.assertEqual(sum(b["count"] for b in result["histogram"]), 4)
        self.assertEqual(result["histogram"][-1]["count"], 1)
        self.assertIsNone(Numeric().finish()["mean"])
        same = Numeric()
        same.add(5)
        same.add(5)
        self.assertEqual(len(same.finish()["histogram"]), 1)
        with self.assertRaises(ValueError):
            same.add("NaN")

    def test_caps_withhold_biased_prefix_distributions(self):
        with patch("tracefront_data.eda.CAP", 2):
            p = profile_table([{"id":"a"},{"id":"b"},{"id":"c"},{"id":"c"}], schema(id="string"), "fixture", "fixture")
        counts = p["categories"]["id"]
        self.assertIsNone(counts["distinct_nonnull"])
        self.assertEqual(counts["distinct_lower_bound"], 3)
        self.assertEqual(counts["top"], [])
        numeric = Numeric(cap=2)
        for value in [1, 2, 3]:
            numeric.add(value)
        self.assertIsNone(numeric.finish()["quantiles"])
        self.assertEqual(numeric.finish()["mean"], "2")

    def test_pdp_censoring_units_and_repeat_extractions(self):
        columns = schema(mean="string", commod="string", conunit="string", concen="decimal", lod="decimal",
                         annotate="string", sample_pk="string", pestcode="string")
        columns["columns"]["concen"]["unit_column"] = "conunit"
        columns["columns"]["lod"]["unit_column"] = "conunit"
        base = {"mean":"ND", "commod":"XX", "conunit":"M", "concen":None, "lod":Decimal("0.01"),
                "annotate":"", "sample_pk":"001", "pestcode":"001"}
        rows = [base, base | {"mean":"NP"}, base | {"mean":"O", "concen":Decimal("0.1")},
                base | {"mean":"R", "concen":Decimal("0.2")},
                base | {"mean":"O", "conunit":"B", "concen":Decimal(5), "sample_pk":"002"}]
        original = copy.deepcopy(rows)
        p = profile_table(rows, columns, "usda_pdp", "results")
        inv = p["investigation"]
        self.assertEqual(p["categories"]["mean"]["all_counts"], {"ND":1,"NP":1,"O":2,"R":1})
        self.assertEqual(inv["detected_groups_with_both_original_and_reextraction"], 1)
        self.assertEqual(inv["assays_per_represented_sample"]["rows"], 5)
        self.assertEqual(p["numeric"]["concen [M]"]["count"], 2)
        self.assertEqual(p["numeric"]["concen [B]"]["count"], 1)
        self.assertEqual(rows, original)
        self.assertFalse(any("exceedance" in r or "contaminated" in r for r in rows))

    def test_noaa_missing_slots_flags_and_partitioned_values(self):
        columns = schema(station_id="string", element="string", unit="string", observation_date="date",
                         observation_status="string", measurement_flag="string", quality_flag="string", source_flag="string", value="decimal")
        row = {"station_id":"S", "element":"TMAX", "unit":"degC", "observation_date":date(2024,1,1),
               "observation_status":"reported_unflagged", "measurement_flag":" ", "quality_flag":" ",
               "source_flag":"a", "value":Decimal(30)}
        rows = [row, row | {"observation_date":date(2024,1,3), "observation_status":"quality_flagged", "quality_flag":"K", "value":Decimal(40)},
                row | {"observation_date":date(2024,1,4), "observation_status":"publisher_missing", "value":None}]
        p = profile_table(rows, columns, "noaa_ghcn_daily", "daily_observations")
        series = p["investigation"]["series"][0]
        self.assertEqual(series["absent_calendar_slots_in_span"], 1)
        self.assertEqual(series["statuses"]["publisher_missing"], 1)
        self.assertEqual(series["quality_flags"], {"<BLANK>":2, "K":1})
        self.assertEqual(p["null_counts"]["value"], 1)
        self.assertEqual(len(p["numeric"]), 2)

    def test_openfda_event_counts_dates_and_empty_objects_are_context(self):
        columns = schema(event_id="string", recall_number="string", openfda="json", recall_initiation_date="date",
                         report_date="date", termination_date="date", center_classification_date="date")
        row = {"event_id":"E", "recall_number":"R1", "openfda":{}, "recall_initiation_date":date(2024,1,3),
               "report_date":date(2024,1,2), "termination_date":None, "center_classification_date":None}
        p = profile_table([row, row | {"recall_number":"R2"}], columns, "openfda_enforcement", "recalls")
        self.assertEqual(p["investigation"]["event_id_profile"]["keys_with_multiple_records"], 1)
        self.assertEqual(p["investigation"]["date_order_audit"]["report_date_before_recall_initiation_date"], 2)
        self.assertEqual(p["null_counts"]["openfda"], 0)
        self.assertEqual(p["investigation"]["date_order_audit"]["empty_openfda_object"], 2)
        self.assertNotIn("contaminated", p)

    def test_opendosm_annual_semantics_and_conflict_evidence_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rejects.jsonl"
            rows = [{"raw_values":{"state":"Johor", "crop_type":"industrial", "production":value},
                     "reason_codes":["conflicting_aggregate_key_all_versions_quarantined"], "row_identifier":"key", "source_row_number":i}
                    for i,value in enumerate(["0.0", "100.0"],1)]
            path.write_text("".join(json.dumps(r) + "\n" for r in rows))
            before = path.read_bytes()
            p = inspect_rejections(path)
            self.assertEqual(p["conflicting_key_groups"], 1)
            self.assertEqual(p["conflicting_groups_with_zero_and_nonzero"], 1)
            self.assertEqual(p["conflicting_key_groups_by_state"], {"Johor":1})
            self.assertEqual(p["rejected_rows"], 2)
            self.assertEqual(path.read_bytes(), before)
        result = profile_table([{"reference_date":date(2017,1,1), "reference_year":2017}],
                               schema(reference_date="date", reference_year="integer"), "opendosm_crops_state", "crops_state")
        self.assertEqual(result["dates"]["reference_date"]["min"], "2017-01-01")
        self.assertNotIn("reference_year [unspecified]", result["numeric"])
        self.assertNotIn("publication_date", result)

    def test_raw_openfda_absence_is_not_explicit_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw.json"
            path.write_text(json.dumps({"results":[{}, {"x":None}, {"x":""}, {"x":0}, {"x":{}}]}))
            before = path.read_bytes()
            result = inspect_openfda_presence(path)
            self.assertEqual(result["fields"]["x"], {"absent":1,"null":1,"empty_string":1,"provided":1,"empty_object":1})
            self.assertEqual(path.read_bytes(), before)

    def test_producer_hash_mismatch_fails_before_upstream_read(self):
        with patch("tracefront_data.eda.sha256_file", return_value="different"), patch("tracefront_data.eda.verify_cleaned") as verify:
            with self.assertRaisesRegex(ValueError, "producer code"):
                verify_inputs(Path("."), {"cleaning_code_sha256":{"clean.py":"expected"}})
            verify.assert_not_called()

    def test_reports_deterministic_and_html_escaped(self):
        audit = {"sources":{"fixture<script>":{"intended_ml_role":"EXTERNAL_CONTEXT_SOURCE", "tables":{}, "limitations":[]}}}
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            write_reports(audit, directory)
            first = {p.name:p.read_bytes() for p in directory.iterdir()}
            write_reports(audit, directory)
            self.assertEqual(first, {p.name:p.read_bytes() for p in directory.iterdir()})
            self.assertIn("fixture&lt;script&gt;", (directory / "m3_eda_visuals.html").read_text())

    def test_documentation_parser_preserves_flag_case(self):
        text = "MFLAG1     is\n  B = estimated\nQFLAG1     is\n  K = failed streak\nSFLAG1     is\n  a = lowercase source\nMFLAG2     is"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "readme.txt"
            path.write_text(text)
            p = noaa_flag_documentation(path)
            self.assertEqual(p["definitions_first_line_from_pinned_readme"]["source"], {"a":"lowercase source"})


if __name__ == "__main__":
    unittest.main()
