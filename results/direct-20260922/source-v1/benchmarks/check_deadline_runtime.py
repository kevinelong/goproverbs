"""Real-runtime deadline recovery and full-history ko legality gate."""
import argparse
import json
from pathlib import Path
import time

from guidance import Broker, choose
from lab import GTP, Referee, ROOT
from neural import KataGo, config_text, digest, hardware, make_query


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    runtime = Path.home() / 'ai_bench/katago'
    exe = runtime / 'opencl-1.18.1/katago.exe'
    model = runtime / 'kata1-b10c128-s919229184-d169515535.txt.gz'
    engine = ROOT / 'target/release/goproverbs.exe'
    config = output / 'analysis.cfg'
    config.write_text(config_text(200), encoding='ascii')
    record = {'status': 'running', 'hashes': {str(p): digest(p) for p in
              (exe, model, engine, config, Path(__file__), ROOT/'benchmarks/neural.py', ROOT/'benchmarks/guidance.py')},
              'before': hardware()}
    try:
        for name in ('round-20260920', 'overnight-20260916'):
            assert not (Path.home() / 'ai_bench' / name / 'RUNNING.lock').exists()
        assert len(record['before']['ollama']['stdout'].strip().splitlines()) <= 1
        with KataGo(exe, model, config, output) as kata:
            record['version'] = kata.request({'id': 'version', 'action': 'query_version'}, deadline=time.perf_counter()+30)
            kata.request(make_query('warmup', [], 'B', 19, 7.5, 'policy'), deadline=time.perf_counter()+30)
            record['loaded'] = hardware()
            query = make_query('forced-timeout', [], 'B', 19, 7.5, 'search')
            query['overrideSettings'] = {'maxTime': .5}
            started = time.perf_counter()
            try:
                kata.request(query, deadline=started + .002)
                raise AssertionError('forced timeout did not occur')
            except TimeoutError:
                record['forced_timeout_ms'] = (time.perf_counter() - started) * 1000
            recovered = kata.request(make_query('after-timeout', [], 'B', 19, 7.5, 'policy'), deadline=time.perf_counter()+2)
            assert recovered['id'] == 'after-timeout' and not kata.cancel_pending
            history = [['B', m] for m in ('A2', 'B1', 'C2')] + [['W', m] for m in ('B2', 'A3', 'C3', 'B4')] + [['B', 'B3']]
            ref = Referee(19, 7.5)
            with GTP(engine, size=19, time_ms=200, search_mode='hybrid') as gp:
                gp.command('komi 7.5')
                for color, move in history:
                    ref.play(color, move)
                    gp.command(f'play {color} {move}')
                try:
                    gp.command('play W B2')
                    raise AssertionError('Rust allowed ko recapture')
                except RuntimeError as exc:
                    assert 'illegal move' in str(exc), str(exc)
                response = kata.request(make_query('ko-history', history, 'W', 19, 7.5, 'policy'), deadline=time.perf_counter()+2)
                assert response['policy'][17*19+1] < 0, 'KataGo allowed ko recapture'
                record['full_history_ko'] = {'rust_rejected': True, 'katago_policy_B2': response['policy'][17*19+1], 'moves': history}
                ref.compare(gp.command('showboard'))
                with Broker(kata) as broker:
                    move, trace = choose(gp, broker, history, 'W', 7.5, 'NN', 200)
                    ref.play('W', move)
                    ref.compare(gp.command('showboard'))
                    record['NN_bridge'] = {'move': move, 'trace': trace}
                    record['broker'] = {'errors': broker.errors, 'metrics': broker.metrics}
                    assert not broker.errors
            record['kata_metrics'] = dict(kata.metrics)
            record['status'] = 'complete'
    except BaseException as exc:
        record['status'] = 'failed'
        record['error'] = repr(exc)
        raise
    finally:
        record['after'] = hardware()
        (output/'result.json').write_text(json.dumps(record, indent=2), encoding='ascii')
    print(json.dumps({k: record[k] for k in ('status', 'forced_timeout_ms', 'kata_metrics', 'broker')}, indent=2))


if __name__ == '__main__': main()
