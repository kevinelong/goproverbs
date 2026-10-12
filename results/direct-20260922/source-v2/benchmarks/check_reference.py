"""Fixed-depth full-width alpha-beta versus unpruned minimax on 5x5 fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
from lab import GTP, ROOT, load_cases, setup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; choose a new file')
    exe = ROOT / 'target/release/goproverbs.exe'
    fixtures = ROOT / 'benchmarks/fixtures.json'
    rows = []
    for case in (c for c in load_cases(fixtures) if c['size'] == 5):
        modes = {}
        for mode in ['full', 'minimax']:
            with GTP(exe, size=5, nodes=1000000, depth=3, beam=1, search_mode=mode, time_ms=10000) as engine:
                setup(engine, case)
                report = engine.command(f"gp-search {case['color']}")
                fields = dict(p.split('=', 1) for p in report.splitlines()[0].split())
                assert fields['depth'] == '3' and fields['limited'] == 'false'
                modes[mode] = fields
        assert modes['full']['move'] == modes['minimax']['move']
        assert modes['full']['score'] == modes['minimax']['score']
        assert int(modes['full']['nodes']) <= int(modes['minimax']['nodes'])
        rows.append({'id': case['id'], 'modes': modes, 'agreement': True})
        print(f"{case['id']}: agreement, nodes {modes['full']['nodes']} vs {modes['minimax']['nodes']}", flush=True)
    result = {'cases': rows, 'depth': 3, 'node_limit': 1000000, 'time_ms':10000,
              'score_comparison_precision': 'GTP output rounded to 0.001; Rust oracle tests use 1e-10',
              'executable_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
              'fixtures_sha256': hashlib.sha256(fixtures.read_bytes()).hexdigest(),
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'referee_sha256': hashlib.sha256((ROOT / 'benchmarks/lab.py').read_bytes()).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='ascii')


if __name__ == '__main__':
    main()
