"""M7 leakage audit and M8 portable, versioned modeling handoff. No model training.

Reproduce after frozen M1/M2/M5 inputs exist:
  PYTHONPATH=src python -m tracefront_data.modeling_handoff
Read safely using load_model_ready(Path.cwd()); it returns X, y, identifiers.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import platform
import tempfile

from tracefront_data.audit import sha256_file
from tracefront_data.cleaning.common import read_table
from tracefront_data.enrichment import (
    DIRECTORY, M2, M5, PLAN, SUMMARY, TABLE, TASK, check_pins, dump, load,
    pins, publish, run as run_enrichment, verify_upstream, write_table,
)
from tracefront_data.pdp_sample_context_features import feature_columns, feature_names

CANDIDATE_DIR = 'data/interim/modeling/m7_v1'
DATASET = 'chemical_imidacloprid_detection_training_v1'
FINAL = 'data/processed/' + DATASET + '.csv'
MANIFEST = 'data/processed/' + DATASET + '.features.json'
READINESS = 'data/processed/' + DATASET + '.readiness.json'
TARGET = 'imidacloprid_detected'
SAFE_FEATURES = tuple(n for n in feature_names() if n != 'pdp_variety_text')
ID_COLUMNS = ('observation_id', 'pdp_sample_id', 'pdp_source_row_number', 'pdp_result_source_row_number')
META_COLUMNS = ('collection_date', 'observation_time', 'source_release', 'analyte_code')
FORBIDDEN = ('result_mean', 'result_concen', 'result_concen_raw', 'result_concen_missing_reason',
             'result_annotate', 'result_confmethod', 'result_confmethod2', 'result_quantitate',
             'result_extract', 'result_determin', 'result_lod', 'result_lab', 'result_testclass',
             'contaminated', 'unsafe_food', 'pesticide_exceedance', 'recall_status',
             'previous_positive_rate', 'full_history_count', 'future_weather', 'supplier_id',
             'pdp_variety_text')
LIMITATIONS = [
    'Retrospective supervised association study of the released 2024 PDP cohort only. Digital context and outcomes were released together; pre-assay public availability and operational prospective validation are unproved.',
    'Detection depends on analyte/commodity assay sensitivity and sampling program; ND is not zero residue, absence of all pesticides, safe food or legal compliance. No tolerance comparison or regulatory exceedance target.',
    'One fixed parent analyte (967 Imidacloprid); metabolites and other analytes are excluded. No sample-level any-pesticide label or untested negative manufactured.',
    'One re-extraction excluded under a prespecified conservative original-result policy; NP would be excluded as marginal-performing nondetect. This selection can affect estimand and missingness.',
    'Temporal collection-date holdout measures later-2024 cohort association, not a model trainable during 2024: all labels were published after the cohort. No future-year generalization is established.',
    'No verified lot, farm, supplier or facility grouping; repeated upstream entities may remain. Do not claim new-farm/facility performance or representative population prevalence.',
    'Imbalanced observed target; use prevalence baseline and class-aware metrics. Person B owns fitting, calibration, explanation and evaluation; no model or accuracy claim produced here.',
    'Country null mixes domestic non-applicability and unknown origin. Quantity null is unknown, never zero. Native categorical tokens are not harmonized; variety text remains withheld.',
    'No cross-source or historical features; NOAA ambient weather is not cold-chain telemetry. Pending FSIS, inspections and sensor datasets remain unavailable.',
    'Actual IBM Z LinuxONE/s390x runtime has not been tested. Portable stdlib CSV/JSON path validated locally on x86_64 only.',
]


def validate_task(task: dict) -> None:
    if (task['dataset'], task['analyte_code'], task['analyte_name'], task['target']) != (DATASET, '967', 'Imidacloprid', TARGET):
        raise ValueError('Task/target changed; a new reviewed dataset version is required')
    if (task['positive_mean_codes'], task['negative_mean_codes'], task['excluded_mean_codes']) != (['O'], ['ND'], ['NP', 'R']):
        raise ValueError('Unreviewed target/censoring policy')
    if tuple(task['safe_features']) != SAFE_FEATURES:
        raise ValueError('Safe feature whitelist changed')
    if (task['available_at_upper_bound'], task['observation_time']) != ('2025-12-23', '2025-12-24'):
        raise ValueError('Unreviewed release/cutoff policy')
    if task['recommended_split']['time_column'] != 'collection_date' or task['recommended_split']['group_column'] != 'pdp_sample_id':
        raise ValueError('Split/group policy changed')
    if not {'BIOLOGICAL', 'COLD_CHAIN'} <= task['blocked_tasks'].keys():
        raise ValueError('Pending domains must remain explicitly blocked')


def assert_safe_features(names) -> None:
    names = list(names)
    if len(names) != len(set(names)) or set(names) - set(SAFE_FEATURES):
        raise ValueError('Forbidden or unapproved feature; explicit whitelist required')


def candidate_columns(root: Path) -> dict:
    features = load(root, M5.replace('.csv', '.schema.json'))['columns']
    columns = {n: {'datatype': 'integer' if n.endswith('row_number') else 'string', 'classification': 'IDENTIFIER_ONLY'} for n in ID_COLUMNS}
    columns.update({n: {'datatype': 'date' if n in {'collection_date', 'observation_time'} else 'string', 'classification': 'METADATA_ONLY'} for n in META_COLUMNS})
    columns.update({n: {**features[n], 'classification': 'SAFE_FEATURE'} for n in SAFE_FEATURES})
    columns[TARGET] = {'datatype': 'integer', 'classification': 'TARGET', 'domain': [0, 1]}
    return columns


def make_candidates(enriched: list[dict], task: dict) -> tuple[list[dict], dict]:
    validate_task(task)
    counts = Counter(r['pdp_sample_id'] for r in enriched)
    reasons = Counter()
    excluded = []
    rows = []
    for r in enriched:
        key = r['pdp_sample_id']
        reason = None
        if counts[key] != 1:
            reason = 'ambiguous_sample_analyte_all_rows_excluded'
        elif r['result_duplicate_of_source_row'] is not None:
            reason = 'exact_analytical_duplicate'
        elif r['result_mean'] in {'NP', 'R'}:
            reason = 'excluded_mean_' + r['result_mean']
        elif r['result_mean'] not in {'O', 'ND'}:
            raise ValueError('Unreviewed analytical outcome code')
        if reason:
            reasons[reason] += 1
            excluded.append({'pdp_sample_id': key, 'pdp_result_source_row_number': r['result_source_row_number'], 'reason': reason})
            continue
        # Target evidence only, NEVER predictors. Preserve censoring distinctions upstream.
        mean, concentration = r['result_mean'], r['result_concen']
        if r['result_pestcode'] != task['analyte_code'] or r['result_conunit'] != 'M':
            raise ValueError('Analyte or concentration-unit scope changed')
        if mean == 'O' and (concentration is None or not concentration.is_finite() or concentration <= 0):
            raise ValueError('Original detection lacks positive finite concentration evidence')
        if mean == 'ND' and (concentration is not None or r['result_concen_missing_reason'] != 'censored_ND'):
            raise ValueError('Nondetect censoring inconsistent; no label guessed')
        if r['result_sample_pk'] != key:
            raise ValueError('Sample provenance mismatch')
        if not r['collection_date'] < date.fromisoformat(task['available_at_upper_bound']) < r['observation_time']:
            raise ValueError('Temporal cutoff not proven')
        row = dict(observation_id='PDP2024:' + key + ':967', pdp_sample_id=key,
                   pdp_source_row_number=r['pdp_source_row_number'],
                   pdp_result_source_row_number=r['result_source_row_number'],
                   collection_date=r['collection_date'], observation_time=r['observation_time'],
                   source_release='PDP_2024', analyte_code='967')
        row.update({n: r[n] for n in SAFE_FEATURES})
        row[TARGET] = int(mean == 'O')
        rows.append(row)
    if len(rows) + len(excluded) != len(enriched):
        raise ValueError('Candidate exclusions do not reconcile')
    return rows, {'input_rows': len(enriched), 'candidate_rows': len(rows), 'excluded_rows': len(excluded),
                  'exclusion_reasons': dict(sorted(reasons.items())), 'excluded_records': excluded,
                  'repeated_sample_groups_before_exclusion': sum(n > 1 for n in counts.values())}


def validate_candidates(rows: list[dict], columns: dict, task: dict) -> dict:
    validate_task(task)
    assert_safe_features(task['safe_features'])
    if set(columns) != set(ID_COLUMNS + META_COLUMNS + SAFE_FEATURES + (TARGET,)):
        raise ValueError('Unexpected column in candidate schema')
    seen, samples, nulls, target_counts = set(), set(), Counter(), Counter()
    domains = {n: Counter() for n in SAFE_FEATURES if columns[n]['datatype'] == 'string'}
    numeric = {n: [] for n in SAFE_FEATURES if columns[n]['datatype'] == 'integer'}
    nullable = {'pdp_import_origin_country_code', 'pdp_sample_unit_count'}
    for row in rows:
        if set(row) != set(columns):
            raise ValueError('Candidate/schema columns differ')
        if type(row['pdp_sample_id']) is not str or type(row['observation_id']) is not str:
            raise ValueError('Invalid stable identifier datatype')
        if row['observation_id'] in seen or row['pdp_sample_id'] in samples:
            raise ValueError('Duplicate sample protection: analytical rows must never cross splits')
        seen.add(row['observation_id']); samples.add(row['pdp_sample_id'])
        if row['observation_id'] != 'PDP2024:' + row['pdp_sample_id'] + ':967':
            raise ValueError('Observation identity/provenance changed')
        for name, spec in columns.items():
            value = row[name]
            if value is None:
                if name not in nullable:
                    raise ValueError('Missing required target/feature/metadata: ' + name)
                nulls[name] += 1
                continue
            expected = {'string': str, 'integer': int, 'date': date}[spec['datatype']]
            if type(value) is not expected:
                raise ValueError('Invalid stable datatype: ' + name)
            if isinstance(value, str) and not value:
                raise ValueError('Empty string outside approved feature domain')
        if row[TARGET] not in (0, 1):
            raise ValueError('Invalid detection target')
        if row['source_release'] != 'PDP_2024' or row['analyte_code'] != '967':
            raise ValueError('Source/analyte provenance changed')
        if row['observation_time'] != date(2025, 12, 24) or row['collection_date'].year != 2024:
            raise ValueError('Temporal cutoff enforcement failed')
        if not date.fromisoformat(task['available_at_upper_bound']) < row['observation_time']:
            raise ValueError('Inputs not available before observation cutoff')
        for n in ('pdp_source_row_number', 'pdp_result_source_row_number'):
            if row[n] <= 0:
                raise ValueError('Invalid source-row provenance')
        count = row['pdp_sample_unit_count']
        if count is not None and count < 0:
            raise ValueError('Impossible negative sample-unit count')
        # Re-derive every calendar feature during independent readback.
        d = row['collection_date']
        if (row['pdp_collection_dow_iso'], row['pdp_collection_doy'], row['pdp_collection_isoweek']) != (d.isoweekday(), d.timetuple().tm_yday, d.isocalendar().week):
            raise ValueError('Calendar feature formula changed')
        target_counts[row[TARGET]] += 1
        for n in domains:
            if row[n] is not None:
                domains[n][row[n]] += 1
        for n in numeric:
            if row[n] is not None:
                numeric[n].append(row[n])
    if not rows or set(target_counts) != {0, 1}:
        raise ValueError('Both detection classes required for this candidate')
    return {'rows': len(rows), 'columns': len(columns), 'unique_samples': len(samples),
            'unique_observation_ids': len(seen), 'target_counts': {str(k): v for k, v in sorted(target_counts.items())},
            'missingness': dict(sorted(nulls.items())),
            'categorical_domains': {n: dict(sorted(v.items())) for n, v in domains.items()},
            'numeric_ranges': {n: {'min': min(v), 'max': max(v)} for n, v in numeric.items()},
            'collection_date_min': min(r['collection_date'] for r in rows).isoformat(),
            'collection_date_max': max(r['collection_date'] for r in rows).isoformat(),
            'no_duplicate_sample': True, 'temporal_cutoff_proven': True, 'target_feature_separation': True}


def split_audit(rows: list[dict]) -> dict:
    """A deterministic, date-aligned split recommendation; no preprocessing fitted."""
    groups = {}
    for r in rows:
        groups.setdefault(r['collection_date'], []).append(r)
    parts = {'train': [], 'validation': [], 'test': []}
    cumulative = 0
    for day in sorted(groups):
        part = 'train' if cumulative < .70 * len(rows) else 'validation' if cumulative < .85 * len(rows) else 'test'
        parts[part].extend(groups[day])
        cumulative += len(groups[day])
    sample_sets = [set(r['pdp_sample_id'] for r in part) for part in parts.values()]
    if any(sample_sets[i] & sample_sets[j] for i in range(3) for j in range(i + 1, 3)):
        raise ValueError('Sample groups overlap across proposed splits')
    if any(not part or {r[TARGET] for r in part} != {0, 1} for part in parts.values()):
        raise ValueError('Both classes and nonempty proposed partitions required; do not weaken split')
    a, b, c = parts.values()
    if not max(r['collection_date'] for r in a) < min(r['collection_date'] for r in b) <= max(r['collection_date'] for r in b) < min(r['collection_date'] for r in c):
        raise ValueError('Temporal partitions overlap')
    return {'method': 'TEMPORAL_COLLECTION_PERIOD_RETROSPECTIVE', 'no_sample_overlap': True,
            'partitions': {name: {'rows': len(part), 'min_date': min(r['collection_date'] for r in part).isoformat(),
                           'max_date': max(r['collection_date'] for r in part).isoformat(),
                           'target_counts': dict(sorted(Counter(str(r[TARGET]) for r in part).items()))}
                           for name, part in parts.items()},
            'limitation': 'Released cohort study only; not a prospective 2024 backtest. No label-availability assumption at earlier collection boundaries.'}


def classifications(root: Path, columns: dict) -> dict:
    result = {n: spec['classification'] for n, spec in columns.items()}
    schema = load(root, DIRECTORY + '/' + TABLE + '.schema.json')
    for n in schema['columns']:
        if n in result:
            continue
        if n == 'pdp_variety_text':
            category = 'QUESTIONABLE'
        elif n in {'result_source_row_number', 'result_sample_pk'}:
            category = 'IDENTIFIER_ONLY'
        elif n in {'result_commod', 'result_commtype', 'result_pestcode', 'result_duplicate_of_source_row'}:
            category = 'METADATA_ONLY'
        elif n in {'result_lab', 'result_testclass', 'result_lod', 'result_conunit', 'result_extract', 'result_determin'}:
            category = 'QUESTIONABLE'
        else:
            category = 'LEAKAGE'
        result[n] = category
    return result


def audit_m7(root: Path) -> tuple[list[dict], dict, dict]:
    validation = load(root, 'reports/m6_validation.json')
    if validation['status'] != 'COMPLETE':
        raise ValueError('M6 gate not passed')
    check_pins(root, validation['inputs']); check_pins(root, validation['outputs'])
    check_pins(root, validation['code_sha256'])
    task = load(root, TASK)
    enriched = list(read_table(root / DIRECTORY / (TABLE + '.csv')))
    rows, exclusions = make_candidates(enriched, task)
    columns = candidate_columns(root)
    profile = validate_candidates(rows, columns, task)
    splits = split_audit(rows)
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary)
        write_table(stage / (DATASET + '.csv'), rows, columns, 'CANDIDATE_M7_PASSED', task['unit_of_observation'])
        if validate_candidates(list(read_table(stage / (DATASET + '.csv'))), columns, task) != profile:
            raise ValueError('Independent candidate typed readback failed')
        publish(stage, root / CANDIDATE_DIR)
    classification = classifications(root, columns)
    findings = {'milestone': 'M7', 'status': 'COMPLETE', 'candidate': DATASET,
                'candidate_path': CANDIDATE_DIR + '/' + DATASET + '.csv',
                'model_ready_candidate': True, 'target': TARGET, 'target_contract': task['target_meaning'],
                'safe_features': list(SAFE_FEATURES), 'column_classification': classification,
                'forbidden_features': list(FORBIDDEN), 'exclusions': exclusions, 'profile': profile,
                'split_recommendation': task['recommended_split'], 'split_audit': splits,
                'leakage_findings': {'known_leakage_features_remaining': [],
                    'analytical_target_evidence_removed_from_features': True,
                    'whitelist_only': True, 'historical_features': [],
                    'full_analytical_panel_not_expanded': True,
                    'availability_scope': 'Retrospective public release study only; no pre-collection availability asserted.',
                    'feature_cutoff': 'All context available by 2025-12-23 < observation_time 2025-12-24; no historical aggregates.'},
                'blocked_tasks': task['blocked_tasks'], 'limitations': LIMITATIONS,
                'inputs': pins(root, [TASK, 'reports/m6_validation.json', SUMMARY, DIRECTORY + '/' + TABLE + '.csv', DIRECTORY + '/' + TABLE + '.schema.json']),
                'code_sha256': pins(root, ['src/tracefront_data/modeling_handoff.py']),
                'outputs': pins(root, [CANDIDATE_DIR + '/' + DATASET + ext for ext in ('.csv', '.schema.json')]),
                'training_performed': False}
    dump(root / 'reports/m7_validation.json', findings)
    lines = ['# M7 leakage and modeling validation', '', 'COMPLETE for the named retrospective chemical detection task. Biological and cold-chain domains remain blocked.', '',
             '**One row:** ' + task['unit_of_observation'], '', '**Target:** ' + task['target_meaning'], '',
             '## Explicit column classification', '', '| Column | Classification |', '| --- | --- |']
    lines += ['| ' + n + ' | ' + c + ' |' for n, c in classification.items()]
    lines += ['', '## Exclusions and duplication', '', json.dumps(exclusions, indent=2), '',
              'All ambiguous sample/analyte groups would be excluded in full; no arbitrary first-row resolution. Split unit is the source sample, not an assay panel row. Sample IDs and lineage are never features. Unknown lots/farms cannot be protected by fabricated groups.', '',
              '## Temporal proof and split', '', findings['leakage_findings']['feature_cutoff'], '', task['recommended_split']['policy'], '',
              task['recommended_split']['rationale'], '', json.dumps(splits, indent=2), '',
              'No future recall, inspection, full-history aggregate, weather window, label-derived category, assay result or ID is admitted by the default feature whitelist.', '',
              '## Scientific limits', ''] + ['- ' + s for s in LIMITATIONS]
    lines += ['', 'Full row counts, categorical domains, missingness, numeric ranges, provenance pins and all candidate classifications: `m7_validation.json`.', '']
    report = '\n'.join(lines)
    (root / 'reports/m7_validation_report.md').write_text(report, encoding='utf-8')
    (root / 'reports/data_leakage_audit.md').write_text(report.replace('# M7 leakage and modeling validation', '# Final Person A leakage audit — M7'), encoding='utf-8')
    return rows, columns, findings


def feature_manifest(root: Path, task: dict, findings: dict) -> dict:
    m5_features = {f['feature']: f for f in feature_columns()}
    numeric = [n for n in SAFE_FEATURES if m5_features[n]['datatype'] == 'integer']
    categorical = [n for n in SAFE_FEATURES if n not in numeric]
    return {'dataset': DATASET, 'version': '1.0', 'schema_version': '1.0',
            'FEATURES': list(SAFE_FEATURES), 'TARGET': TARGET,
            'IDENTIFIER_ONLY': list(ID_COLUMNS), 'METADATA_ONLY': list(META_COLUMNS),
            'FORBIDDEN': list(FORBIDDEN), 'unknown_columns': 'REJECT',
            'numeric_features': numeric, 'categorical_features': categorical,
            'feature_contracts': {n: {**m5_features[n], 'source': 'usda_pdp.samples',
                'available_at_upper_bound': task['available_at_upper_bound'],
                'observation_time': task['observation_time'],
                'prediction_time_availability': 'Verified release-time retrospective only, not prospective 2024',
                'leakage_assessment': 'Sample context/calendar, independent of analytical results; identifier and outcome inputs forbidden',
                'missingness': 'Null unknown, never zero' if n == 'pdp_sample_unit_count' else
                    'Null domestic non-applicability or unknown import origin; consult origin code' if n == 'pdp_import_origin_country_code' else
                    'Required non-null native value; literal codes preserved'} for n in SAFE_FEATURES},
            'categorical_domains': findings['profile']['categorical_domains'],
            'missingness': findings['profile']['missingness'], 'null_encoding': r'\N',
            'reader': 'tracefront_data.modeling_handoff.load_model_ready or cleaning.common.read_table; do not use dataframe default NA/type guessing',
            'forbidden_behavior': 'No inference of labels from recalls/conditions; no history from this table without a newly reviewed availability contract.'}


def handoff_m8(root: Path, rows: list[dict], columns: dict, findings: dict) -> dict:
    if findings['status'] != 'COMPLETE' or findings['leakage_findings']['known_leakage_features_remaining']:
        raise ValueError('M7 leakage gate failed')
    task = load(root, TASK)
    processed = root / 'data/processed'
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary)
        write_table(stage / (DATASET + '.csv'), rows, columns, 'MODEL_READY_RETROSPECTIVE', task['unit_of_observation'])
        if validate_candidates(list(read_table(stage / (DATASET + '.csv'))), columns, task) != findings['profile']:
            raise ValueError('M8 typed schema/profile readback failed')
        publish(stage, processed)
    manifest = feature_manifest(root, task, findings)
    # Verify existing manifests before reusing versioned output; changed contracts need a new version.
    if (root / MANIFEST).exists() and load(root, MANIFEST) != manifest:
        raise ValueError('Versioned feature manifest changed')
    dump(root / MANIFEST, manifest)
    source = load(root, 'reports/m1_source_manifest.json')
    m6 = load(root, SUMMARY)
    provenance = {'raw_artifacts': {name: [{k: a.get(k) for k in ('artifact_id', 'path', 'sha256', 'size_bytes', 'source_url', 'retrieved_at', 'source_version')}
                    for a in info['artifacts'] if a['status'] == 'captured'] for name, info in source['datasets'].items()},
                  'training_source': 'USDA AMS PDP 2024 only; other source artifacts are acquisition context, not inputs to predictors or target.',
                  'publisher_member_evidence': m6['publisher_evidence'],
                  'versions': {'M1': 'frozen 20261017T060123145416Z-29c44de9 receipt', 'cleaning': 'm2_v1',
                    'canonical_schema': 'configs/source_contracts.json (source-specific M4 mappings)', 'features': 'm5_v1',
                    'enrichment': 'm6_v1 J01 only', 'leakage_audit': 'm7_v1', 'dataset': '1.0'},
                  'stage_fingerprints': pins(root, ['reports/m1_source_manifest.json', 'reports/m2_cleaning_summary.json',
                    'configs/source_contracts.json', 'reports/m5_validation.json', 'reports/m6_validation.json',
                    'reports/m7_validation.json', TASK, PLAN, 'src/tracefront_data/enrichment.py', 'src/tracefront_data/modeling_handoff.py']),
                  'raw_immutability': m6['raw_integrity_after']}
    dump(root / ('data/processed/' + DATASET + '.provenance.json'), provenance)
    readiness = {'dataset': DATASET, 'version': '1.0', 'model_ready': True,
                 'readiness_scope': 'RETROSPECTIVE_RELEASE_COHORT_ONLY', 'prospective_deployment_ready': False,
                 'task': 'binary_classification', 'domain': 'CHEMICAL', 'target': TARGET,
                 'schema_version': '1.0', 'dataset_path': FINAL,
                 'dataset_sha256': sha256_file(root / FINAL), 'feature_manifest_path': MANIFEST,
                 'feature_manifest_sha256': sha256_file(root / MANIFEST),
                 'schema_sha256': sha256_file((root / FINAL).with_suffix('.schema.json')),
                 'provenance_sha256': sha256_file(root / ('data/processed/' + DATASET + '.provenance.json')),
                 'leakage_audit_passed': True, 'leakage_audit_path': 'reports/m7_validation.json',
                 'leakage_audit_sha256': sha256_file(root / 'reports/m7_validation.json'),
                 'recommended_split': task['recommended_split'], 'group_column': 'pdp_sample_id',
                 'time_column': 'collection_date', 'observation_time': task['observation_time'],
                 'rows': len(rows), 'columns': len(columns), 'unit_of_observation': task['unit_of_observation'],
                 'training_performed': False}
    dump(root / READINESS, readiness)
    handoff = {'milestone': 'M8', 'status': 'COMPLETE', 'person_a_workflow_complete': True,
               'datasets': [{**readiness, 'readiness_path': READINESS, 'target_meaning': task['target_meaning'],
                   'positive_class': '1 = publisher MEAN O (original-extraction imidacloprid detection)',
                   'negative_class': '0 = publisher MEAN ND (validated well-recovered nondetect)',
                   'features': manifest, 'profile': findings['profile'], 'split_audit': findings['split_audit'],
                   'timestamps': {'collection_date': 'Specimen calendar date, no availability implication',
                       'observation_time': '2025-12-24, fixed retrospective release cutoff'},
                   'temporal_cutoffs': findings['leakage_findings']['feature_cutoff'], 'limitations': LIMITATIONS}],
               'task_readiness': {'CHEMICAL': {'status': 'MODEL_READY', 'reason': 'Original imidacloprid detection; retrospective release-cohort scope only.'},
                   'BIOLOGICAL': {'status': 'BLOCKED', 'reason': task['blocked_tasks']['BIOLOGICAL']},
                   'COLD_CHAIN': {'status': 'BLOCKED', 'reason': task['blocked_tasks']['COLD_CHAIN']}},
               'provenance': provenance,
               'reproduction_command': 'PYTHONPATH=src python -m tracefront_data.modeling_handoff --rebuild-check',
               'workflow': 'Frozen raw → M2 clean → verify M4/M5 → M6 J01 → M7 leakage/target audit → M8 processed dataset',
               'portability': {'formats': ['UTF-8 CSV with LF and declared null escaping', 'UTF-8 JSON'],
                   'python_minimum': '3.11', 'runtime_dependencies': 'Python standard library, including sqlite3 for upstream cleaning',
                   'native_data_dependencies_added': [], 'architecture_assumptions': 'No endian, SIMD or x86 instructions in the data path',
                   'tested_architecture': platform.machine(), 's390x_executed': False,
                   'known_s390x_issues': 'No data-format issue known; actual interpreter/sqlite3 and target execution need verification. Person B modeling dependencies are a separate unresolved s390x concern.'},
               'person_b_contract': {'existing': 'food-risk-ml/docs/data_contract.md is Salmonella/FSIS-only and is NOT applicable to this chemical dataset.',
                   'required_adapter': 'Separate chemical loader using this readiness/whitelist. Do not rename detection to salmonella_positive or pesticide_exceedance. Do not call existing FSIS training entrypoint on these files.',
                   'compatible_invariants': 'Source sample groups, target/ID exclusion, whole-day chronological splits, both classes per partition, fit preprocessing on training only; no estimated label-lag history.'},
               'training_performed': False}
    dump(root / 'reports/modeling_handoff.json', handoff)
    write_handoff_report(root, handoff)
    return handoff


def write_handoff_report(root: Path, handoff: dict) -> None:
    d = handoff['datasets'][0]; f = d['features']
    lines = ['# Person A model-ready handoff — M8', '',
             'Person A workflow COMPLETE. CHEMICAL MODEL_READY for the named retrospective detection task only. BIOLOGICAL and COLD_CHAIN remain BLOCKED. No ML model was trained.', '',
             '## Dataset and target contract', '',
             f"- Dataset/version: `{DATASET}` / 1.0; binary classification.",
             f"- File: `{FINAL}`; {d['rows']:,} rows, {d['columns']} columns.",
             f"- SHA-256: `{d['dataset_sha256']}`.",
             '- One row represents ' + d['unit_of_observation'],
             '- Target: `' + TARGET + '`. ' + d['target_meaning'],
             '- Positive class: ' + d['positive_class'],
             '- Exclusions: one re-extraction in this release; any NP or ambiguous repeated sample/analyte group is excluded by policy. All other analytes outside scope.', '',
             '## Person B input contract', '',
             f"Read `{READINESS}` and require `model_ready is true`, verify all pinned hashes, then use `{MANIFEST}`. `load_model_ready(Path.cwd())` performs these checks and returns (X records, y values, identifier/metadata records).",
             '', '- Numeric: ' + ', '.join('`' + n + '`' for n in f['numeric_features']),
             '- Categorical: ' + ', '.join('`' + n + '`' for n in f['categorical_features']),
             '- IDENTIFIER_ONLY: ' + ', '.join('`' + n + '`' for n in ID_COLUMNS),
             '- METADATA_ONLY: ' + ', '.join('`' + n + '`' for n in META_COLUMNS),
             '- FORBIDDEN: ' + ', '.join('`' + n + '`' for n in FORBIDDEN), '',
             'Only explicit FEATURES may enter the default matrix; unknown names are rejected. Do not train on IDs, timestamps, outcome evidence or remaining columns selected by exclusion. Full classification of every candidate/enriched column is in `reports/m7_validation.json`.', '',
             '## Feature formulas, availability and missingness', '',
             'Every feature has a typed source/formula, leakage assessment, availability and missingness contract in the feature manifest. Native product/origin/claim/count fields pass through unchanged; weekday/day-of-year/ISO-week derive only from collection_date. No analytical result contributes to a feature.', '',
             r'CSV null is \N. Empty string is distinct; non-null leading backslashes are escaped. Use the provided typed reader rather than default dataframe NA/type inference. IDs stay strings; missing quantity stays missing; country null can mean domestic non-applicability or unknown origin. Fit any imputation/encoding using training only.', '',
             'All context has a verified public availability upper bound of 2025-12-23, before the fixed retrospective observation_time of 2025-12-24. This does not prove inputs were publicly available at collection or before assays. No historical feature is delivered.', '',
             '## Split and evaluation', '', d['recommended_split']['policy'], '', d['recommended_split']['rationale'], '',
             'Use the deterministic boundaries and partition counts in `reports/m7_validation.json` (`split_audit`). Group on `pdp_sample_id`; time column `collection_date`. Report prevalence, class-aware metrics and sampling/assay sensitivity caveats. No geographic/facility transfer claim is supported. Person B owns fitting, tuning, calibration, SHAP and final evaluation.', '',
             '## Joins and pending tasks', '',
             'M6 evaluated 14 formal proposals: J01 same-release exact SAMPLE_PK approved; five cross-context joins rejected; eight proposals pending. No recall/weather/OpenDOSM history attached. See `reports/m6_join_audit.md` and JSON for every key, clock, cardinality, ambiguity and scientific decision.', '',
             'BIOLOGICAL: BLOCKED_PENDING_FSIS. Official raw pathogen samples and dictionary not acquired. FDA inspections remain pending independently and cannot substitute pathogen labels.', '',
             'COLD_CHAIN: BLOCKED_PENDING_SENSOR_DATA. No legitimate specimen-linked sensor/storage/microbial dataset. Ambient NOAA is not refrigeration telemetry. Concentration regression and regulatory exceedance also remain outside the ready task.', '',
             '## Frozen provenance and reproducibility', '',
             'Raw paths, source URLs/retrieval clocks and SHA-256 hashes for all captured sources are in the adjacent `.provenance.json`; only the pinned PDP 2024 archive contributes training rows. M1 source manifest/receipt, M2 cleaning, M4 source schema, M5 features, M6 enrichment and M7 audit are versioned and pinned. The 2024 ZIP includes the reviewed dictionary and code workbook.', '',
             'With the frozen raw store present, run from the repository root:', '',
             '```bash', 'PYTHONPATH=src python -m tracefront_data.clean',
             'PYTHONPATH=src python -m tracefront_data.pdp_sample_context_features',
             'PYTHONPATH=src python -m tracefront_data.modeling_handoff --rebuild-check',
             'PYTHONPATH=src python -m tracefront_data.modeling_handoff --verify-only',
             'PYTHONPATH=src python -m unittest discover -s tests -q', '```', '',
             'The handoff command automatically executes M6, checks M7, then publishes M8. Existing versioned data must match a fresh build or the command refuses overwrite. `--rebuild-check` performs two independent raw-to-M2 cleaning rebuilds, reconstructs M5 from those samples, and regenerates final data with byte comparison. Missing raw inputs stop the workflow; no automatic acquisition/version substitution occurs. Restore exact M1 receipts and maintain offline raw backups.', '',
             '## IBM Z LinuxONE', '',
             'Portable UTF-8 CSV/JSON, Python 3.11+ standard library, SQLite for upstream cleaning. No pandas/NumPy/Parquet/native data wheel required. Actual s390x execution is untested; only local x86_64 Python 3.11.17/3.14.7 is verified. Validate target Python/sqlite3 before regeneration. Model-library portability belongs to Person B.', '',
             '## Existing Person B integration', '',
             handoff['person_b_contract']['existing'], '', handoff['person_b_contract']['required_adapter'], '',
             '## Scientific interpretation boundaries', ''] + ['- ' + x for x in LIMITATIONS]
    lines += ['', '## Recommended Person B next prompt', '',
              '> Begin M9 baseline training only for entries with model_ready=true in reports/modeling_handoff.json. Use chemical_imidacloprid_detection_training_v1.csv, target imidacloprid_detected, and exactly the feature whitelist after readiness/checksum validation. Build a separate chemical task loader; the existing FSIS contract is incompatible. Use the documented whole-day collection-date holdout with sample groups and train-only preprocessing. Treat evaluation as retrospective released-cohort association, not prospective 2024 or unsafe-food/exceedance prediction. Keep biological and cold-chain tasks blocked. Verify IBM Z LinuxONE/s390x model dependencies before training. You own fitting, comparison, tuning, calibration, SHAP and final evaluation.', '']
    (root / 'reports/modeling_handoff.md').write_text('\n'.join(lines), encoding='utf-8')


def load_model_ready(root: Path, feature_list=None):
    """Fail-closed Person B reader; no dependency on or alteration of FSIS code."""
    ready = load(root, READINESS)
    if ready.get('model_ready') is not True or ready.get('leakage_audit_passed') is not True:
        raise ValueError('Dataset is not MODEL_READY')
    if ready['dataset'] != DATASET or ready['target'] != TARGET or ready['dataset_path'] != FINAL:
        raise ValueError('Dataset/task readiness mismatch')
    check_pins(root, {FINAL: ready['dataset_sha256'], MANIFEST: ready['feature_manifest_sha256'],
        FINAL.replace('.csv', '.schema.json'): ready['schema_sha256'],
        'data/processed/' + DATASET + '.provenance.json': ready['provenance_sha256'],
        'reports/m7_validation.json': ready['leakage_audit_sha256']})
    manifest = load(root, MANIFEST)
    provenance = load(root, 'data/processed/' + DATASET + '.provenance.json')
    check_pins(root, provenance['stage_fingerprints'])
    if tuple(manifest['FEATURES']) != SAFE_FEATURES or manifest['TARGET'] != TARGET:
        raise ValueError('Feature manifest whitelist mismatch')
    names = list(SAFE_FEATURES if feature_list is None else feature_list)
    assert_safe_features(names)
    task = load(root, TASK)
    rows = list(read_table(root / FINAL))
    profile = validate_candidates(rows, candidate_columns(root), task)
    expected_profile = load(root, 'reports/m7_validation.json')['profile']
    if profile != expected_profile or len(rows) != ready['rows']:
        raise ValueError('Final profile/domain/provenance does not match M7')
    return ([{n: r[n] for n in names} for r in rows], [r[TARGET] for r in rows],
            [{n: r[n] for n in ID_COLUMNS + META_COLUMNS} for r in rows])


def run(root: Path) -> dict:
    run_enrichment(root)
    rows, columns, findings = audit_m7(root)
    return handoff_m8(root, rows, columns, findings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--rebuild-check', action='store_true')
    args = parser.parse_args()
    root = Path.cwd()
    if args.verify_only:
        x, y, ids = load_model_ready(root)
        verify_upstream(root)
        print(json.dumps({'model_ready': True, 'rows': len(y), 'features': len(x[0]), 'unique_samples': len({i['pdp_sample_id'] for i in ids})}))
    else:
        result = run(root)
        if args.rebuild_check:
            from tracefront_data.reproduce_handoff import rebuild_check
            rebuild_check(root)
        print(json.dumps({'status': result['status'], 'datasets': [{k: d[k] for k in ('dataset', 'rows', 'columns', 'dataset_sha256', 'model_ready')} for d in result['datasets']]}, indent=2))


if __name__ == '__main__':
    main()
