"""Independent frozen-raw rebuild proof for M8; standard library only."""
from datetime import date
from pathlib import Path
import platform
import tempfile

from tracefront_data.clean import run_cleaning
from tracefront_data.cleaning.common import read_table
from tracefront_data.enrichment import (
    DIRECTORY, M2, M5, TABLE, TASK, attach, check_pins, context_index,
    dump, load, pins, selected_results, verify_upstream, write_table,
)
from tracefront_data.modeling_handoff import (
    CANDIDATE_DIR, DATASET, FINAL, candidate_columns, load_model_ready,
    make_candidates, validate_candidates,
)
from tracefront_data.pdp_sample_context_features import (
    assemble_row, build_schema, feature_names, load_assessment,
)
from tracefront_data.audit import sha256_file
import csv
import json
from tracefront_data.cleaning.common import encode


def rebuild_check(root: Path) -> dict:
    """Clean every eligible source from frozen raw twice, then rebuild M5–M8.

    Temporary clean outputs never replace M2 or M5. Every independently
    generated M2 file and selected M5/M6/M8 byte stream must match frozen
    outputs, not merely a re-copy or metadata-only verification.
    """
    source, before = verify_upstream(root)
    clean_summary = load(root, 'reports/m2_cleaning_summary.json')
    contract, scope, _ = load_assessment(root)
    task = load(root, TASK)
    columns = candidate_columns(root)
    baseline = pins(root, [FINAL, FINAL.replace('.csv', '.schema.json'), M5,
                          M5.replace('.csv', '.schema.json'), DIRECTORY + '/' + TABLE + '.csv',
                          DIRECTORY + '/' + TABLE + '.schema.json'])
    rounds = []
    for iteration in (1, 2):
        print(f'Independent frozen-raw rebuild {iteration}/2: M2 cleaning all eligible sources', flush=True)
        with tempfile.TemporaryDirectory(dir=root / 'data/interim', prefix='.m8-rebuild-') as temporary:
            directory = Path(temporary)
            clean_dir = directory / 'm2'
            rebuilt = run_cleaning(root, root / 'reports/m1_source_manifest.json', clean_dir.relative_to(root))
            if rebuilt['outputs'] != clean_summary['outputs']:
                raise ValueError('Raw-to-M2 rebuild differs from frozen 30-file checksum map')
            samples = list(read_table(clean_dir / 'usda_pdp/samples.csv'))
            features = [assemble_row(r) for r in samples]
            m5_csv = directory / 'pdp_sample_context_features.csv'
            names = ['pdp_source_row_number', 'pdp_sample_id', *feature_names()]
            with m5_csv.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.writer(stream, lineterminator='\n'); writer.writerow(names)
                for row in features:
                    writer.writerow(encode(row[n]) for n in names)
            m5_csv.with_suffix('.schema.json').write_text(json.dumps(
                build_schema(contract, scope, scope['decision_contract']['prediction_cutoff']),
                indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            for generated, pinned in [(m5_csv, root / M5), (m5_csv.with_suffix('.schema.json'), (root / M5).with_suffix('.schema.json'))]:
                if sha256_file(generated) != sha256_file(pinned):
                    raise ValueError('Fresh M5 formula/schema rebuild differs')
            index = context_index(features, samples)
            enriched = [attach(r, index, task['observation_time']) for r in selected_results(
                clean_dir / 'usda_pdp/results.csv', task['analyte_code'])]
            result_columns = json.loads((clean_dir / 'usda_pdp/results.schema.json').read_text())['columns']
            m5_columns = json.loads(m5_csv.with_suffix('.schema.json').read_text())['columns']
            m6_columns = {'result_' + n: spec for n, spec in result_columns.items()}
            m6_columns.update(m5_columns)
            m6_columns.update(collection_date={'datatype': 'date'}, observation_time={'datatype': 'date'}, source_release={'datatype': 'string'})
            m6_csv = directory / (TABLE + '.csv')
            write_table(m6_csv, enriched, m6_columns, 'NOT MODEL-READY',
                        'One selected imidacloprid analytical result linked to the identical release specimen context')
            for suffix in ('.csv', '.schema.json'):
                if sha256_file(m6_csv.with_suffix(suffix)) != sha256_file(root / DIRECTORY / (TABLE + suffix)):
                    raise ValueError('Fresh M6 identity/provenance rebuild differs')
            candidates, exclusions = make_candidates(enriched, task)
            profile = validate_candidates(candidates, columns, task)
            final = directory / (DATASET + '.csv')
            write_table(final, candidates, columns, 'MODEL_READY_RETROSPECTIVE', task['unit_of_observation'])
            if sha256_file(final) != baseline[FINAL] or sha256_file(final.with_suffix('.schema.json')) != baseline[FINAL.replace('.csv', '.schema.json')]:
                raise ValueError('Fresh raw-to-final output bytes differ')
            if sha256_file(final) != sha256_file(root / CANDIDATE_DIR / (DATASET + '.csv')):
                raise ValueError('Fresh M7 candidate differs')
            rounds.append({'round': iteration, 'm2_files_matched': len(rebuilt['outputs']),
                           'm5_csv_schema_byte_identical': True, 'm6_csv_schema_byte_identical': True,
                           'm7_candidate_byte_identical': True, 'final_csv_schema_byte_identical': True,
                           'dataset_sha256': sha256_file(final), 'rows': profile['rows'],
                           'exclusions': exclusions['exclusion_reasons']})
        check_pins(root, baseline)
        print(f'Independent frozen-raw rebuild {iteration}/2: all bytes match', flush=True)
    _, after = verify_upstream(root)
    if before != after:
        raise ValueError('Raw integrity changed during independent rebuilds')
    x, y, identifiers = load_model_ready(root)
    result = {'status': 'PASS', 'python': platform.python_version(), 'architecture': platform.machine(),
              'independent_raw_to_final_rounds': rounds, 'raw_immutability_before': before,
              'raw_immutability_after': after, 'm5_inputs_unchanged': True,
              'final_readiness_reader': {'rows': len(y), 'features': len(x[0]), 'unique_samples': len({i['pdp_sample_id'] for i in identifiers})},
              'format_nondeterminism': 'None observed: CSV and schema bytes identical across independent rebuilds.',
              'source_code_sha256': pins(root, ['src/tracefront_data/reproduce_handoff.py']),
              's390x_executed': False, 'training_performed': False}
    dump(root / 'reports/m8_rebuild_validation.json', result)
    return result
