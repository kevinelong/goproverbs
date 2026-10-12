"""Compare full deepcopy with history-preserving container copies, no inference."""
import copy
import json
from pathlib import Path
import statistics
import time

from lab import Referee
from neural import digest


if __name__ == '__main__':
    base = Path('results/neural-led-20260923/screen-v1')
    state = json.loads((base/'status.json').read_text())
    log = base/(state['active']+'.jsonl')
    game = next(g for g in json.loads((base/'schedule.json').read_text()) if g['stem'] == state['active'])
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    moves = game['opening']['moves']+[[r['color'], r['move']] for r in rows[:-1]]
    ref = Referee(19, 7.5)
    for color, move in moves:
        ref.play(color, move)
    final = rows[-1]
    result = dict(input_sha256=digest(log), history_moves=len(moves), seen_positions=len(ref.seen),
                  failed_decision_ms=final['ms'], modes={},
                  note='20 warm-process CPU repetitions; isolated copy/play diagnostic, not engine throughput.')
    expected = copy.deepcopy(ref)
    expected.play(final['color'], final['move'])
    for mode in ('deepcopy', 'container_copy'):
        times = []
        for _ in range(20):
            start = time.perf_counter()
            if mode == 'deepcopy':
                child = copy.deepcopy(ref)
            else:
                child = copy.copy(ref)
                child.board, child.seen = ref.board.copy(), ref.seen.copy()
            child.play(final['color'], final['move'])
            times.append((time.perf_counter()-start)*1000)
            assert vars(child) == vars(expected)
            assert child.board is not ref.board and child.seen is not ref.seen
        result['modes'][mode] = dict(median_ms=statistics.median(times), max_ms=max(times), samples_ms=times)
    output = base.parent/'copy-diagnosis.json'
    with output.open('x', encoding='ascii') as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps(result, indent=2))
