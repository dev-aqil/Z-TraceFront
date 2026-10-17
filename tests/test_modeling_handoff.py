"""M7/M8 contracts: target semantics, temporal/group protection and fail-closed input."""
import ast
import copy
from datetime import date, timedelta
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tracefront_data.cleaning.common import read_table
from tracefront_data.enrichment import DIRECTORY, TABLE, TASK, write_table
from tracefront_data.modeling_handoff import (
    DATASET, FINAL, FORBIDDEN, ID_COLUMNS, MANIFEST, META_COLUMNS, READINESS,
    SAFE_FEATURES, TARGET, assert_safe_features, candidate_columns, classifications,
    load_model_ready, make_candidates, split_audit, validate_candidates, validate_task,
)

ROOT = Path(__file__).resolve().parents[1]


class TargetAndWhitelistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task = json.loads((ROOT / TASK).read_text())
        cls.source = list(read_table(ROOT / DIRECTORY / (TABLE + '.csv')))
        cls.rows, cls.exclusions = make_candidates(cls.source, cls.task)
        cls.columns = candidate_columns(ROOT)

    def test_publisher_target_semantics_and_exclusions(self):
        counts = {0: 0, 1: 0}
        for row in self.rows:
            counts[row[TARGET]] += 1
        self.assertEqual(counts, {0: 9481, 1: 390})
        self.assertEqual(self.exclusions['exclusion_reasons'], {'excluded_mean_R': 1})
        self.assertEqual(len(self.rows), 9871)

    def test_np_remains_excluded_not_an_ordinary_negative(self):
        row = copy.deepcopy(self.source[0])
        row['result_mean'] = 'NP'
        rows, exclusions = make_candidates([row], self.task)
        self.assertEqual(rows, [])
        self.assertEqual(exclusions['exclusion_reasons'], {'excluded_mean_NP': 1})

    def test_unknown_code_and_missing_detection_evidence_refused(self):
        row = copy.deepcopy(self.source[0])
        row['result_mean'] = 'UNKNOWN'
        with self.assertRaisesRegex(ValueError, 'Unreviewed analytical'):
            make_candidates([row], self.task)
        row['result_mean'] = 'O'; row['result_concen'] = None
        with self.assertRaisesRegex(ValueError, 'lacks positive'):
            make_candidates([row], self.task)

    def test_nondetect_numeric_concentration_never_guessed(self):
        row = copy.deepcopy(self.source[0])
        row['result_mean'] = 'ND'; row['result_concen'] = Decimal('.01')
        with self.assertRaisesRegex(ValueError, 'censoring inconsistent'):
            make_candidates([row], self.task)

    def test_all_ambiguous_sample_versions_excluded(self):
        a = copy.deepcopy(self.source[0]); b = copy.deepcopy(a)
        b['result_source_row_number'] += 1
        rows, exclusions = make_candidates([a, b], self.task)
        self.assertEqual(rows, [])
        self.assertEqual(exclusions['excluded_rows'], 2)

    def test_target_and_identifiers_never_in_feature_matrix(self):
        assert_safe_features(SAFE_FEATURES)
        self.assertFalse(set(SAFE_FEATURES) & set(ID_COLUMNS + META_COLUMNS + (TARGET,)))
        for name in (TARGET, *ID_COLUMNS, *META_COLUMNS, *FORBIDDEN, 'innocently_named_new_column'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                assert_safe_features([*SAFE_FEATURES, name])

    def test_future_history_and_label_proxies_rejected(self):
        for name in ('previous_event_count', 'full_history_positive_rate', 'future_recall_count',
                     'pathogen_positive', 'contaminated', 'pesticide_exceedance', 'truck_temperature'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                assert_safe_features([name])

    def test_stable_whitelist_cannot_promote_questionable_column(self):
        task = copy.deepcopy(self.task)
        task['safe_features'].append('pdp_variety_text')
        with self.assertRaisesRegex(ValueError, 'whitelist changed'):
            validate_task(task)
        self.assertEqual(len(SAFE_FEATURES), 9)

    def test_target_cannot_be_renamed_to_exceedance_or_salmonella(self):
        for target in ('pesticide_exceedance', 'salmonella_positive', 'contaminated'):
            task = copy.deepcopy(self.task); task['target'] = target
            with self.assertRaisesRegex(ValueError, 'new reviewed dataset'):
                validate_task(task)

    def test_pending_domains_stay_blocked(self):
        self.assertTrue(self.task['blocked_tasks']['BIOLOGICAL'].startswith('BLOCKED_PENDING_FSIS'))
        self.assertTrue(self.task['blocked_tasks']['COLD_CHAIN'].startswith('BLOCKED_PENDING_SENSOR_DATA'))
        task = copy.deepcopy(self.task); del task['blocked_tasks']['BIOLOGICAL']
        with self.assertRaisesRegex(ValueError, 'Pending domains'):
            validate_task(task)

    def test_every_enriched_and_final_column_classified(self):
        classes = classifications(ROOT, self.columns)
        schema = json.loads((ROOT / DIRECTORY / (TABLE + '.schema.json')).read_text())
        self.assertFalse(set(schema['columns']) - set(classes))
        self.assertFalse(set(self.columns) - set(classes))
        self.assertEqual(classes['result_mean'], 'LEAKAGE')
        self.assertEqual(classes['pdp_variety_text'], 'QUESTIONABLE')
        self.assertEqual(classes[TARGET], 'TARGET')
        self.assertEqual({n for n, c in classes.items() if c == 'SAFE_FEATURE'}, set(SAFE_FEATURES))

    def test_candidate_schema_domains_nulls_and_unique_ids(self):
        result = validate_candidates(self.rows, self.columns, self.task)
        self.assertEqual(result['rows'], 9871)
        self.assertEqual(result['unique_samples'], 9871)
        self.assertEqual(result['target_counts'], {'0': 9481, '1': 390})
        self.assertTrue(result['temporal_cutoff_proven'])

    def test_duplicate_sample_protection(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate sample'):
            validate_candidates([self.rows[0], self.rows[0]], self.columns, self.task)

    def test_temporal_cutoff_enforced(self):
        r = copy.deepcopy(self.rows[0]); r['observation_time'] = date(2025, 12, 23)
        with self.assertRaisesRegex(ValueError, 'Temporal cutoff'):
            validate_candidates([r], self.columns, self.task)
        r = copy.deepcopy(self.source[0]); r['observation_time'] = date(2024, 1, 1)
        with self.assertRaisesRegex(ValueError, 'Temporal cutoff'):
            make_candidates([r], self.task)

    def test_schema_impossible_value_and_missing_target_rejected(self):
        for column, bad in [(TARGET, None), ('pdp_sample_unit_count', -1), ('pdp_collection_doy', 500),
                            ('pdp_sample_id', 123), ('analyte_code', '967-metabolite')]:
            r = copy.deepcopy(self.rows[0]); r[column] = bad
            with self.subTest(column=column), self.assertRaises(ValueError):
                validate_candidates([r], self.columns, self.task)

    def test_deterministic_candidates_and_output_bytes(self):
        rows, exclusions = make_candidates(copy.deepcopy(self.source), self.task)
        self.assertEqual(rows, self.rows)
        self.assertEqual(exclusions, self.exclusions)
        with tempfile.TemporaryDirectory() as temporary:
            a, b = Path(temporary) / 'a.csv', Path(temporary) / 'b.csv'
            for path in (a, b):
                write_table(path, rows, self.columns, 'MODEL_READY_RETROSPECTIVE', self.task['unit_of_observation'])
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(list(read_table(a)), self.rows)

    def test_whole_day_split_has_both_classes_and_no_group_overlap(self):
        split = split_audit(self.rows)
        self.assertTrue(split['no_sample_overlap'])
        parts = list(split['partitions'].values())
        self.assertEqual(sum(p['rows'] for p in parts), len(self.rows))
        self.assertLess(parts[0]['max_date'], parts[1]['min_date'])
        self.assertLess(parts[1]['max_date'], parts[2]['min_date'])
        self.assertTrue(all(set(p['target_counts']) == {'0', '1'} for p in parts))

    def test_duplicate_sample_cannot_leak_across_split_dates(self):
        rows = copy.deepcopy(self.rows)
        rows[-1]['pdp_sample_id'] = rows[0]['pdp_sample_id']
        with self.assertRaisesRegex(ValueError, 'groups overlap'):
            split_audit(rows)

    def test_split_refuses_single_class_partition(self):
        rows = copy.deepcopy(self.rows)
        for r in rows:
            r[TARGET] = 0
        with self.assertRaisesRegex(ValueError, 'Both classes'):
            split_audit(rows)

    def test_source_unit_and_sample_identity_mismatch_rejected(self):
        for name, value in [('result_conunit', 'B'), ('result_pestcode', 'AHF'), ('result_sample_pk', 'wrong')]:
            r = copy.deepcopy(self.source[0]); r[name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                make_candidates([r], self.task)


class ReaderGateTests(unittest.TestCase):
    def test_model_ready_must_be_boolean_true(self):
        for flag in (False, None, 'true', 1):
            with patch('tracefront_data.modeling_handoff.load', return_value={'model_ready': flag}):
                with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, 'not MODEL_READY'):
                    load_model_ready(ROOT)

    def test_readiness_target_mismatch_rejected(self):
        r = dict(model_ready=True, leakage_audit_passed=True, dataset=DATASET,
                 target='salmonella_positive', dataset_path=FINAL)
        with patch('tracefront_data.modeling_handoff.load', return_value=r):
            with self.assertRaisesRegex(ValueError, 'readiness mismatch'):
                load_model_ready(ROOT)


class PersonBPortableGuardTests(unittest.TestCase):
    """Run unchanged Person B pure guards via AST; pandas/model stack not imported.

    This checks the compatible guard subset only, not the FSIS loader or training
    stack. Those dependencies are absent and that biological contract is pending.
    """
    def test_existing_person_b_pure_leakage_guard_accepts_safe_features(self):
        source = ROOT / 'food-risk-ml/src/features/leakage.py'
        tree = ast.parse(source.read_text())
        selected = []
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'DENYLIST' for t in node.targets):
                selected.append(node)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in {'LeakageError', 'leakage_hits', 'assert_no_leaky_features'}:
                selected.append(node)
        ns = {}
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), 'exec'), ns)
        ns['assert_no_leaky_features'](list(SAFE_FEATURES))
        for name in (TARGET, 'result_mean', 'recall_status', 'salmonella_positive'):
            with self.subTest(name=name), self.assertRaises(ns['LeakageError']):
                ns['assert_no_leaky_features']([name])

class FinalArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        provenance_path = 'data/processed/' + DATASET + '.provenance.json'
        provenance = json.loads((ROOT / provenance_path).read_text())
        relatives = {FINAL, FINAL.replace('.csv', '.schema.json'), MANIFEST, READINESS,
                     provenance_path, 'reports/m7_validation.json',
                     'data/interim/m5_v1/pdp_sample_context_features.schema.json', TASK}
        relatives.update(provenance['stage_fingerprints'])
        for relative in relatives:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())

    def tearDown(self):
        self.temporary.cleanup()

    def test_final_reader_returns_only_whitelist_target_and_group_metadata(self):
        x, y, ids = load_model_ready(self.root)
        self.assertEqual(len(x), 9871)
        self.assertEqual(set(x[0]), set(SAFE_FEATURES))
        self.assertEqual(sum(y), 390)
        self.assertEqual(len({r['pdp_sample_id'] for r in ids}), 9871)
        self.assertEqual(set(ids[0]), set(ID_COLUMNS + META_COLUMNS))

    def test_reader_rejects_forbidden_feature_selection(self):
        with self.assertRaisesRegex(ValueError, 'Forbidden or unapproved'):
            load_model_ready(self.root, feature_list=[TARGET])

    def test_final_csv_tamper_detected(self):
        path = self.root / FINAL
        path.write_bytes(path.read_bytes() + b'tampered\n')
        with self.assertRaisesRegex(ValueError, 'Pinned artifact changed'):
            load_model_ready(self.root)

    def test_feature_manifest_tamper_detected(self):
        path = self.root / MANIFEST
        m = json.loads(path.read_text()); m['FEATURES'].append(TARGET)
        path.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, 'Pinned artifact changed'):
            load_model_ready(self.root)

    def test_nonready_artifact_refused(self):
        path = self.root / READINESS
        r = json.loads(path.read_text()); r['model_ready'] = False
        path.write_text(json.dumps(r))
        with self.assertRaisesRegex(ValueError, 'not MODEL_READY'):
            load_model_ready(self.root)

    def test_schema_or_provenance_tamper_detected(self):
        path = (self.root / FINAL).with_suffix('.schema.json')
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'Pinned artifact changed'):
            load_model_ready(self.root)


if __name__ == '__main__':
    unittest.main()
