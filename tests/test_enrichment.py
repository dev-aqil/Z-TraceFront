"""M6 regression checks: no invented identity, history or cross-context linkage."""
import copy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from tracefront_data.enrichment import (
    PLAN, attach, context_index, historical_eligible, publish, validate_plan,
)

ROOT = Path(__file__).resolve().parents[1]


class JoinAuditTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((ROOT / PLAN).read_text())

    def test_all_formal_proposals_have_complete_decisions(self):
        validate_plan(self.plan)
        self.assertEqual(len(self.plan['proposals']), 14)

    def test_unsupported_join_cannot_be_enabled_by_flag(self):
        self.plan['proposals'][2]['status'] = 'APPROVED'
        with self.assertRaisesRegex(ValueError, 'Only reviewed'):
            validate_plan(self.plan)

    def test_incomplete_justification_refused(self):
        del self.plan['proposals'][0]['prediction_time_availability']
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            validate_plan(self.plan)

    def test_no_us_malaysia_or_fuzzy_company_or_recall_label_join(self):
        decisions = {p['proposal_id']: p for p in self.plan['proposals']}
        for key in ('J02', 'J03', 'J04', 'J05', 'J06'):
            self.assertEqual(decisions[key]['status'], 'REJECTED')
        self.assertIn('Malaysian station', decisions['J03']['scientific_justification'])
        self.assertIn('Firm text', decisions['J02']['scientific_justification'])
        self.assertIn('not a tested-positive label', decisions['J02']['scientific_justification'])

    def test_unapproved_history_refused(self):
        self.plan['history_features_approved'] = ['previous_event_count']
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            validate_plan(self.plan)

    def test_same_day_future_and_focal_outcomes_excluded(self):
        t = date(2024, 5, 1)
        earlier = date(2024, 4, 1)
        later = date(2024, 6, 1)
        def eligible(event, available, sample='prior'):
            return historical_eligible(event, available, t, 'verified:1', 'verified:1', sample, 'focal')
        self.assertTrue(eligible(earlier, earlier))
        for event, available in [(t, earlier), (later, earlier), (earlier, t), (earlier, later), (earlier, None)]:
            self.assertFalse(eligible(event, available))
        self.assertFalse(eligible(earlier, earlier, 'focal'))

    def test_unknown_or_different_entity_never_counts(self):
        earlier, t = date(2024, 1, 1), date(2024, 2, 1)
        for a, b in [(None, None), ('name', None), ('verified:1', 'verified:2')]:
            self.assertFalse(historical_eligible(earlier, earlier, t, a, b, 'a', 'b'))


class LinkageTests(unittest.TestCase):
    def setUp(self):
        self.sample = {'sample_pk': '001', 'source_row_number': 8, 'collection_date': date(2024, 1, 2)}
        self.feature = {'pdp_sample_id': '001', 'pdp_source_row_number': 8,
                        'pdp_commodity_code': 'AA', 'pdp_commodity_type_code': 'FR'}
        self.result = {'sample_pk': '001', 'source_row_number': 30, 'commod': 'AA', 'commtype': 'FR',
                       'mean': 'NP', 'concen': None, 'conunit': 'M'}

    def test_exact_identity_preserves_censoring_and_provenance(self):
        index = context_index([self.feature], [self.sample])
        before = copy.deepcopy(self.feature)
        row = attach(self.result, index, '2025-12-24')
        self.assertEqual(row['result_mean'], 'NP')
        self.assertIsNone(row['result_concen'])
        self.assertEqual(row['result_source_row_number'], 30)
        self.assertEqual(row['pdp_sample_id'], '001')
        self.assertNotIn('contaminated', row)
        self.assertEqual(before, self.feature)

    def test_duplicate_right_key_prevents_many_to_many(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate right sample'):
            context_index([self.feature], [self.sample, self.sample])
        with self.assertRaisesRegex(ValueError, 'Duplicate or unsupported'):
            context_index([self.feature, self.feature], [self.sample])

    def test_unmatched_and_commodity_mismatch_refused(self):
        with self.assertRaisesRegex(ValueError, 'Unmatched'):
            attach(self.result, {}, '2025-12-24')
        index = context_index([self.feature], [self.sample])
        self.result['commod'] = 'BB'
        with self.assertRaisesRegex(ValueError, 'commodity disagreement'):
            attach(self.result, index, '2025-12-24')

    def test_m5_row_lineage_cannot_change(self):
        self.feature['pdp_source_row_number'] = 7
        with self.assertRaisesRegex(ValueError, 'provenance mismatch'):
            context_index([self.feature], [self.sample])

    def test_deterministic_publication_and_tamper_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage, dest = Path(temporary) / 'stage', Path(temporary) / 'dest'
            stage.mkdir()
            (stage / 'x.csv').write_bytes(b'a,b\n1,2\n')
            publish(stage, dest)
            publish(stage, dest)
            self.assertEqual((dest / 'x.csv').read_bytes(), (stage / 'x.csv').read_bytes())
            (dest / 'x.csv').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'Refusing to overwrite'):
                publish(stage, dest)


if __name__ == '__main__':
    unittest.main()
