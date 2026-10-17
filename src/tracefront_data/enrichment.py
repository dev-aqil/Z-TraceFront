"""M6: formal join audit and the only approved same-release PDP linkage.

No cross-source or historical enrichment is justified by the acquired cohort.
Run from repository root: PYTHONPATH=src python -m tracefront_data.enrichment
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
import zipfile
import io

from tracefront_data.audit import sha256_file
from tracefront_data.clean import verify_baseline
from tracefront_data.cleaning.common import encode, read_table
from tracefront_data.pdp_sample_context_features import load_assessment, verify_outputs
from tracefront_data.provenance import inside_root

DIRECTORY = 'data/interim/enriched/m6_v1'
TABLE = 'pdp_imidacloprid_context'
PLAN = 'configs/m6_join_proposals.json'
TASK = 'configs/m7_chemical_detection_v1.json'
M5 = 'data/interim/m5_v1/pdp_sample_context_features.csv'
M2 = 'data/interim/m2_v1/usda_pdp/'
SUMMARY = 'reports/m6_enrichment_summary.json'
REQUIRED_PROPOSAL_FIELDS = {
    'proposal_id', 'left_source', 'right_source', 'left_unit_of_observation',
    'right_unit_of_observation', 'intended_resulting_unit', 'entity_key', 'geographic_key',
    'temporal_key', 'commodity_product_key', 'expected_join_cardinality', 'timestamp_semantics',
    'prediction_time_availability', 'information_gained', 'ambiguity_risk', 'leakage_risk',
    'deterministic_resolution_strategy', 'scientific_justification', 'status',
}


def load(root: Path, relative: str) -> dict:
    return json.loads(inside_root(root, relative).read_text(encoding='utf-8'))


def dump(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')


def pins(root: Path, paths) -> dict:
    return {p: sha256_file(inside_root(root, p)) for p in sorted(set(paths))}


def check_pins(root: Path, expected: dict) -> None:
    for relative, digest in expected.items():
        if sha256_file(inside_root(root, relative)) != digest:
            raise ValueError('Pinned artifact changed: ' + relative)


def validate_plan(plan: dict) -> None:
    proposals = plan['proposals']
    if len({p['proposal_id'] for p in proposals}) != len(proposals):
        raise ValueError('Duplicate proposal ID')
    for p in proposals:
        if REQUIRED_PROPOSAL_FIELDS - p.keys() or any(not p[k] for k in REQUIRED_PROPOSAL_FIELDS):
            raise ValueError('Incomplete formal join proposal')
        if p['status'] not in {'APPROVED', 'REJECTED', 'PENDING_MORE_INFORMATION'}:
            raise ValueError('Unknown proposal status')
    # This executor cannot be enabled for an unreviewed new relationship by changing a flag.
    if {p['proposal_id'] for p in proposals if p['status'] == 'APPROVED'} != {'J01'}:
        raise ValueError('Only reviewed same-release J01 may execute')
    if plan['cross_source_joins_approved'] != 0 or plan['history_features_approved']:
        raise ValueError('Unsupported cross-source or historical enrichment')


def historical_eligible(event_time: date, available_at: date, observation_time: date,
                        entity_id: str | None, focal_entity_id: str | None,
                        sample_id: str, focal_sample_id: str) -> bool:
    """Strict two-clock invariant for a future approved history; never emits features.

    Missing IDs/availability must be rejected, not guessed. Date-only input must
    represent a completed availability day. No current source qualifies.
    """
    return bool(entity_id and focal_entity_id and entity_id == focal_entity_id
                and sample_id != focal_sample_id and event_time is not None
                and available_at is not None and event_time < observation_time
                and available_at < observation_time)


def verify_upstream(root: Path) -> tuple[dict, dict]:
    load_assessment(root)  # verifies M1–M4 raw, schemas, reports and producer fingerprints
    record = load(root, 'reports/m5_validation.json')
    check_pins(root, {p: v['sha256'] for p, v in record['artifacts'].items()})
    check_pins(root, record['code_sha256'])
    check_pins(root, load(root, 'reports/m2_m5_checkpoint.json')['artifacts'])
    verify_outputs(root / 'data/interim/m5_v1', root / 'reports/m5_pdp_sample_context_features_summary.json')
    source, raw = verify_baseline(root, root / 'reports/m1_source_manifest.json')
    return source, raw


def workbook_evidence(root: Path, source: dict, task: dict) -> dict:
    artifact = next(a for a in source['datasets']['usda_pdp']['artifacts'] if a['artifact_id'] == 'pdp_2024')
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    member = 'PDP ReferenceTables 2024.xlsx'
    with zipfile.ZipFile(root / artifact['path']) as archive:
        data = archive.read(member)
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        strings = [''.join(x.itertext()) for x in ET.fromstring(book.read('xl/sharedStrings.xml')).findall('s:si', ns)]
        rows = []
        for name in sorted(book.namelist()):
            if not name.startswith('xl/worksheets/sheet') or not name.endswith('.xml'):
                continue
            for row in ET.fromstring(book.read(name)).findall('.//s:row', ns):
                cells = []
                for c in row:
                    v = c.find('s:v', ns)
                    value = v.text if v is not None else ''
                    cells.append(strings[int(value)] if c.get('t') == 's' and value else value)
                rows.append(cells)
    analyte = [r for r in rows if len(r) == 4 and r[:2] == [task['analyte_code'], task['analyte_name']]]
    means = {r[0]: r[1] for r in rows if len(r) == 2 and r[0] in {'ND', 'NP', 'O', 'R'} and ('Detect' in r[1])}
    if len(analyte) != 1 or set(means) != {'ND', 'NP', 'O', 'R'}:
        raise ValueError('Publisher analyte/result-code evidence ambiguous')
    if int(analyte[0][3]) != 9872:
        raise ValueError('Declared full-cohort analyte coverage changed')
    from hashlib import sha256
    return {'archive_path': artifact['path'], 'archive_sha256': artifact['sha256'],
            'reference_member': member, 'reference_member_sha256': sha256(data).hexdigest(),
            'analyte_reference_row': analyte[0], 'mean_code_definitions': means,
            'dictionary_member': 'PDP DataDictionary 2024.pdf',
            'dictionary_relationship': 'SAMPLE_PK uniquely identifies samples and is the analytical table foreign key.'}


def selected_results(path: Path, code: str):
    """Filter the pinned typed CSV before conversion; scan ALL records, not a prefix."""
    schema = json.loads(path.with_suffix('.schema.json').read_text())
    convert = {'string': str, 'integer': int, 'date': date.fromisoformat, 'decimal': Decimal}
    with path.open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(schema['columns']):
            raise ValueError('Result header/schema mismatch')
        for row in reader:
            if row['pestcode'] != code:
                continue
            if set(row) != set(schema['columns']) or any(v is None for v in row.values()):
                raise ValueError('Malformed selected analytical row')
            yield {k: None if v == r'\N' else convert[schema['columns'][k]['datatype']](
                v[1:] if v.startswith('\\\\') else v) for k, v in row.items()}


def context_index(features, samples) -> dict:
    context, dates = {}, {}
    for sample in samples:
        key = sample['sample_pk']
        if key in dates:
            raise ValueError('Duplicate right sample key; many-to-many expansion refused')
        dates[key] = sample
    for feature in features:
        key = feature['pdp_sample_id']
        if key in context or key not in dates:
            raise ValueError('Duplicate or unsupported M5 context key')
        sample = dates[key]
        if feature['pdp_source_row_number'] != sample['source_row_number']:
            raise ValueError('M5 source-row provenance mismatch')
        context[key] = {**feature, 'collection_date': sample['collection_date']}
    if set(context) != set(dates):
        raise ValueError('M5/sample coverage mismatch')
    return context


def attach(result: dict, index: dict, observation_time: str) -> dict:
    key = result['sample_pk']
    if key not in index:
        raise ValueError('Unmatched PDP sample; refusing guessed relationship')
    context = index[key]
    if (result['commod'], result['commtype']) != (context['pdp_commodity_code'], context['pdp_commodity_type_code']):
        raise ValueError('Specimen commodity disagreement')
    return {**{'result_' + k: v for k, v in result.items()}, **context,
            'observation_time': date.fromisoformat(observation_time), 'source_release': 'PDP_2024'}


def write_table(path: Path, rows: list[dict], columns: dict, status: str, grain: str) -> None:
    schema = {'schema_version': '1.0', 'status': status, 'row_granularity': grain,
              'columns': columns, 'null_encoding': {'null': r'\N', 'escape': 'Prefix one extra backslash to non-null values starting with backslash', 'empty_string': 'non-null empty string'}}
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(columns)
        for row in rows:
            if set(row) != set(columns):
                raise ValueError('Output row/schema mismatch')
            writer.writerow(encode(row[c]) for c in columns)
    # Column order is part of the contract; do not sort schema keys.
    path.with_suffix('.schema.json').write_text(json.dumps(schema, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def publish(stage: Path, destination: Path) -> None:
    """Reuse equal bytes, refuse changed artifacts; validate all names before writes."""
    destination.mkdir(parents=True, exist_ok=True)
    for src in stage.iterdir():
        target = destination / src.name
        if target.exists() and sha256_file(src) != sha256_file(target):
            raise ValueError('Refusing to overwrite changed artifact: ' + str(target))
    for src in stage.iterdir():
        target = destination / src.name
        if not target.exists():
            target.write_bytes(src.read_bytes())


def run(root: Path) -> dict:
    root = root.resolve()
    plan, task = load(root, PLAN), load(root, TASK)
    validate_plan(plan)
    source, before = verify_upstream(root)
    evidence = workbook_evidence(root, source, task)
    upstream_paths = ['reports/m5_validation.json', 'reports/m2_m5_checkpoint.json', PLAN, TASK,
                      M5, M5.replace('.csv', '.schema.json'), M2 + 'samples.csv', M2 + 'results.csv',
                      M2 + 'samples.schema.json', M2 + 'results.schema.json']
    inputs = pins(root, upstream_paths)
    index = context_index(read_table(root / M5), read_table(root / M2 / 'samples.csv'))
    rows = [attach(r, index, task['observation_time']) for r in selected_results(root / M2 / 'results.csv', task['analyte_code'])]
    if not rows:
        raise ValueError('No acquired selected-analyte rows')
    result_schema = load(root, M2 + 'results.schema.json')['columns']
    feature_schema = load(root, M5.replace('.csv', '.schema.json'))['columns']
    columns = {'result_' + k: v for k, v in result_schema.items()}
    columns.update(feature_schema)
    columns.update(collection_date={'datatype': 'date'}, observation_time={'datatype': 'date'}, source_release={'datatype': 'string'})
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary)
        write_table(stage / (TABLE + '.csv'), rows, columns, 'NOT MODEL-READY', 'One selected imidacloprid analytical result linked to the identical release specimen context')
        # Typed roundtrip before publication.
        if list(read_table(stage / (TABLE + '.csv'))) != rows:
            raise ValueError('M6 typed roundtrip differs')
        publish(stage, root / DIRECTORY)
    check_pins(root, inputs)
    _, after = verify_upstream(root)
    if before != after:
        raise ValueError('Raw verification changed')
    output_files = [DIRECTORY + '/' + TABLE + ext for ext in ('.csv', '.schema.json')]
    groups = Counter(r['result_sample_pk'] for r in rows)
    summary = {'milestone': 'M6', 'status': 'COMPLETE', 'data_status': 'NOT MODEL-READY',
               'proposals': plan['proposals'], 'proposal_status_counts': dict(sorted(Counter(p['status'] for p in plan['proposals']).items())),
               'cross_source_joins_performed': 0, 'same_source_joins_performed': 1, 'history_features': [],
               'inputs': inputs, 'outputs': pins(root, output_files), 'raw_integrity_before': before,
               'raw_integrity_after': after, 'm5_inputs_unchanged': True, 'publisher_evidence': evidence,
               'materialization': {'proposal_id': 'J01', 'rows': len(rows), 'left_selected_rows': len(rows),
                    'matched_rows': len(rows), 'match_rate': 1.0, 'unmatched_rows': 0,
                    'multi_match_rows': 0, 'right_unique_samples': len(index),
                    'distinct_left_samples': len(groups), 'repeated_left_sample_groups': sum(n > 1 for n in groups.values()),
                    'exclusions': 'All non-967 analytes out of scope; no analytical outcome filtering in M6.',
                    'outside_scope_analytical_rows': 2872073 - len(rows)},
               'code_sha256': pins(root, ['src/tracefront_data/enrichment.py']),
               'temporal_safety': 'No historical feature emitted. Strict event AND availability cutoff helper rejects same-day/future/focal/unknown-entity inputs. Contemporaneous context available by prior release day for retrospective study only.',
               'entity_resolution': 'Exact source specimen identity only; no company matching, synthetic supplier IDs or geographic inference.',
               'training_performed': False}
    dump(root / SUMMARY, summary)
    lines = ['# M6 join audit', '', 'COMPLETE. Zero cross-source enrichments approved. One publisher-documented within-release specimen link executed. NOT MODEL-READY.', '',
             'The full formal proposals below were recorded before materialization. No historical counts, rates or weather windows were emitted.', '']
    for p in plan['proposals']:
        lines += ['## ' + p['proposal_id'] + ' — ' + p['status'], '']
        lines += ['- **' + k + '**: ' + str(v) for k, v in p.items() if k != 'proposal_id']
        lines += ['']
    lines += ['## Materialization evidence', '', json.dumps(summary['materialization'], indent=2), '',
              'Source identifiers, all selected analytical evidence including ND/NP/concentration/unit/censoring fields, and M5 context are preserved. All such evidence remains excluded from predictors unless explicitly whitelisted at M7.', '',
              'Strict temporal helper is a tested invariant for future reviews, not permission to generate unapproved history. No current source meets entity/availability/denominator prerequisites.', '',
              'Output checksums and frozen inputs: `m6_enrichment_summary.json`. Reproduce: `PYTHONPATH=src python -m tracefront_data.enrichment`.', '']
    (root / 'reports/m6_join_audit.md').write_text('\n'.join(lines), encoding='utf-8')
    dump(root / 'reports/m6_validation.json', {'milestone': 'M6', 'status': 'COMPLETE',
        'checks': {'formal_proposals_complete': True, 'only_approved_join_executed': True,
                   'no_cross_source_join': True, 'no_row_expansion': True, 'typed_roundtrip': True,
                   'raw_immutable': True, 'm5_inputs_unchanged': True, 'no_history_features': True},
        'inputs': inputs, 'code_sha256': summary['code_sha256'],
        'outputs': pins(root, output_files + [SUMMARY, 'reports/m6_join_audit.md'])})
    return summary


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    result = run(Path.cwd())
    print(json.dumps({k: result[k] for k in ('status', 'proposal_status_counts', 'materialization')}, indent=2))


if __name__ == '__main__':
    main()
