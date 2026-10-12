"""Freeze the prespecified 20-pair NH screening without changing the pilot."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    prior = ROOT / 'results/roadmap-20260921'
    frozen = prior / 'source-final'
    pilot = json.loads((prior / 'arena-v2-200/manifest.json').read_text())
    manifest = json.loads((frozen / 'manifest.json').read_text())
    for name, expected in manifest.items():
        assert digest(frozen / name) == expected, name
    source_hashes = {name: digest(ROOT / name) for name in manifest
                     if name.startswith(('src/', 'tests/')) or name in ('Cargo.toml', 'Cargo.lock')}
    assert all(value == manifest[name] for name, value in source_hashes.items())
    openings_path = prior / 'corpus/openings.json'
    corpus = json.loads(openings_path.read_text())
    chosen = corpus['openings'][2:22]
    pilot_ids = {row['opening'] for row in pilot['records']}
    assert len(chosen) == 20
    assert [row['id'] for row in chosen] == [f'opening-{i:03d}' for i in range(2, 22)]
    assert not pilot_ids.intersection(row['id'] for row in chosen)
    sequences = {tuple(map(tuple, row['moves'])) for row in chosen}
    assert len(sequences) == 20
    assert not sequences.intersection(tuple(map(tuple, row['moves'])) for row in corpus['openings'][:2])
    assert all(len(row['moves']) % 2 == 0 and row['moves'][-1][0] == 'W' for row in chosen)
    fixed = {
        'katago': Path(pilot['settings']['katago']),
        'model': Path(pilot['settings']['model']),
        'exe': prior / 'goproverbs-arena-v2.exe',
        'profile': frozen / 'profiles/baseline.weights',
        'openings': openings_path,
    }
    for key, path in fixed.items():
        expected = pilot['hashes'][pilot['settings'][key]]
        assert digest(path) == expected, key
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output / 'snapshot'
    snapshot.mkdir()
    for folder in ('benchmarks', 'profiles', 'src', 'tests'):
        shutil.copytree(frozen / folder, snapshot / folder)
    arena_source = prior / 'source-arena-v2'
    shutil.copytree(arena_source / 'src', output / 'executable-source/src')
    for name in ('Cargo.toml', 'Cargo.lock'):
        shutil.copy2(frozen / name, snapshot / name)
    shutil.copy2(fixed['exe'], snapshot / 'goproverbs.exe')
    shutil.copy2(prior / 'corpus/positions.json', snapshot / 'positions.json')
    selection = {'seed': corpus['seed'], 'source': str(openings_path),
                 'source_sha256': digest(openings_path), 'excluded_pilot_ids': sorted(pilot_ids),
                 'selection': 'Prespecified original indices [2:22], before observing screening outcomes.',
                 'limitations': 'Unused development openings; not an expert-reviewed pristine holdout.',
                 'openings': chosen}
    (snapshot / 'openings.json').write_text(json.dumps(selection, indent=2), encoding='ascii')
    command = [sys.executable, '-u', str(snapshot / 'benchmarks/roadmap.py'), 'arena',
               '--katago', str(fixed['katago']), '--model', str(fixed['model']),
               '--output', str(output / 'run'), '--exe', str(snapshot / 'goproverbs.exe'),
               '--profile', str(snapshot / 'profiles/baseline.weights'),
               '--corpus', str(snapshot / 'positions.json'), '--openings', str(snapshot / 'openings.json'),
               '--modes', 'NH', '--time-ms', '200', '--pairs', '20']
    plan = {'command': command, 'expected_games': 40, 'expected_complete_pairs': 20,
            'executable_source': str(arena_source), 'harness_source': str(frozen),
            'source_note': 'snapshot/src/tests are final WSL validation revision. executable-source/src is historical arena source, archived without a contemporaneous source manifest. Executable identity is pinned to pilot hash.',
            'selected_opening_ids': [row['id'] for row in chosen],
            'pilot_excluded': True, 'no_tuning_during_screening': True,
            'fixed_external_hashes': {str(path): digest(path) for path in fixed.values()},
            'snapshot_hashes': {path.relative_to(snapshot).as_posix(): digest(path)
                                for path in snapshot.rglob('*') if path.is_file() and '__pycache__' not in path.parts},
            'current_final_source_matches': source_hashes,
            'validation': {'wsl_rust_tests_passed': 47,
                           'provenance': 'Previously observed WSL test pass, reconciled against final source hashes; not a new test run.',
                           'native_windows_full_suite': 'Still blocked by Application Control in historical validation.'}}
    (output / 'plan.json').write_text(json.dumps(plan, indent=2), encoding='ascii')
    print(json.dumps({'output': str(output), 'opening_pairs': len(chosen), 'source_files_matched': len(source_hashes)}))


if __name__ == '__main__':
    main()
