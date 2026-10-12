"""Pretrained KataGo policy/search baselines. No third-party Python packages.

Policy decisions use only raw policy, never searched moveInfos or values.
All requests/responses are preserved; a single synchronous worker avoids
overlapping inference. External executables and weights live outside the repo.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import queue
import random
import statistics
import subprocess
import threading
import time

from lab import COLUMNS, GTP, ROOT, Referee, acceptable, load_cases, setup


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def vertex(index, size):
    if not 0 <= index <= size * size:
        raise ValueError('policy index outside board')
    return 'pass' if index == size * size else f'{COLUMNS[index % size]}{size - index // size}'


def policy_move(response, size):
    values = response['policy']
    if len(values) != size * size + 1 or any(not math.isfinite(p) or p < -1 for p in values):
        raise ValueError('invalid policy array')
    legal = [i for i, p in enumerate(values) if p >= 0]
    if not legal or max(values) <= 0:
        raise ValueError('policy has no positive legal probability')
    return vertex(max(legal, key=lambda i: values[i]), size)


def search_move(response):
    return min(response['moveInfos'], key=lambda row: row['order'])['move']


def make_query(identifier, moves, color, size, komi, mode):
    # Last turn's next player is inferred by KataGo. Reject ambiguous caller
    # state instead of inserting a synthetic pass (which would change history).
    if moves and moves[-1][0] == color:
        raise ValueError('last move must belong to the opponent')
    result = {'id': str(identifier), 'moves': moves, 'initialPlayer': moves[0][0] if moves else color,
              'rules': 'tromp-taylor', 'whiteHandicapBonus': '0', 'komi': komi,
              'boardXSize': size, 'boardYSize': size, 'includePolicy': True,
              'analysisPVLen': 5}
    if mode == 'policy':
        result['maxVisits'] = 1
    return result


class DeadlineResultConsumed(TimeoutError):
    """A late terminal response was already drained; no cancel is necessary."""


class KataGo:
    def __init__(self, exe, model, config, directory, timeout=180):
        self.number = 0
        self.timeout = timeout
        self.lines = queue.Queue()
        self.request_lock = threading.Lock()
        self.cancel_pending = set()
        self.cancel_number = 0
        self.failure = None
        self.metrics = {'sent': 0, 'cancelled': 0, 'late_replies': 0, 'lock_timeouts': 0}
        self.outbound = queue.Queue()
        self.wire = (directory / 'wire.jsonl').open('w', encoding='ascii')
        self.stderr = (directory / 'katago-stderr.txt').open('w', encoding='utf-8')
        try:
            self.proc = subprocess.Popen([str(exe), 'analysis', '-model', str(model), '-config', str(config)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr, text=True,
                cwd=directory, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except BaseException:
            self.stderr.close()
            self.wire.close()
            raise
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        self.writer = threading.Thread(target=self._write, daemon=True)
        self.writer.start()

    def _write(self):
        # A full/stalled OS pipe must not block a caller past its deadline.
        # Serial request/cancellation draining bounds this queue to one query
        # and its cancellation. Shutdown kills a writer-stalling owned process.
        try:
            while True:
                line = self.outbound.get()
                if line is None:
                    return
                self.proc.stdin.write(line)
                self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            self.lines.put(None)

    def _read(self):
        for line in self.proc.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def _send(self, query):
        self.wire.write(json.dumps({'request': query}) + '\n')
        self.wire.flush()
        self.outbound.put(json.dumps(query) + '\n')
        self.metrics['sent'] += 1

    def _receive(self, deadline):
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise TimeoutError('KataGo request deadline expired')
        try:
            line = self.lines.get(timeout=remaining)
        except queue.Empty as exc:
            raise TimeoutError('KataGo response timeout; see katago-stderr.txt') from exc
        if line is None:
            raise RuntimeError('KataGo exited; see katago-stderr.txt')
        response = json.loads(line)
        self.wire.write(json.dumps({'response': response}) + '\n')
        self.wire.flush()
        if 'error' in response or 'warning' in response:
            raise RuntimeError(f'KataGo rejected or altered request: {response}')
        return response

    def request(self, query, deadline=None):
        # Deadlines use perf_counter: Python 3.11 on this Windows host uses
        # 15.625 ms GetTickCount64 for monotonic(), but QPC here is high resolution.
        deadline = time.perf_counter() + self.timeout if deadline is None else deadline
        if not self.request_lock.acquire(timeout=max(0, deadline - time.perf_counter())):
            self.metrics['lock_timeouts'] += 1
            raise TimeoutError('KataGo request queue deadline expired')
        try:
            if self.failure is not None:
                raise RuntimeError(f'KataGo transport failed; restart required: {self.failure}')
            # A terminate acknowledgement alone does not mean inference stopped.
            # Consume both it and the original terminal reply before new work.
            while self.cancel_pending:
                response = self._receive(deadline)
                identifier = response.get('id')
                if identifier not in self.cancel_pending:
                    raise RuntimeError('unexpected response while draining cancellation')
                self.metrics['late_replies'] += 1
                if not response.get('isDuringSearch', False):
                    self.cancel_pending.remove(identifier)
            if time.perf_counter() >= deadline:
                raise TimeoutError('KataGo request expired before submission')
            self._send(query)
            try:
                while True:
                    response = self._receive(deadline)
                    if response.get('id') != query['id']:
                        raise RuntimeError('response id mismatch')
                    if not response.get('isDuringSearch', False):
                        if time.perf_counter() >= deadline:
                            # Already consumed the terminal reply; no cancellation
                            # is needed, but a late result must not enter search.
                            raise DeadlineResultConsumed('KataGo result arrived late')
                        return response
            except DeadlineResultConsumed:
                raise
            except TimeoutError:
                if 'action' in query:
                    # Administrative actions cannot be cancelled as analyses.
                    self.cancel_pending.add(query['id'])
                else:
                    self.cancel_number += 1
                    cancel_id = f'cancel-{self.cancel_number}-{query["id"]}'
                    self.cancel_pending.update((query['id'], cancel_id))
                    self._send({'id': cancel_id, 'action': 'terminate', 'terminateId': query['id']})
                    self.metrics['cancelled'] += 1
                raise
        except TimeoutError:
            raise
        except Exception as exc:
            # An unknown response state cannot safely admit another analysis.
            self.failure = repr(exc)
            raise
        finally:
            self.request_lock.release()

    def choose(self, moves, color, size, komi, mode, initial_stones=None):
        self.number += 1
        started = time.perf_counter()
        query = make_query(self.number, moves, color, size, komi, mode)
        if initial_stones is not None:
            query['initialStones'] = initial_stones
        response = self.request(query)
        if response['rootInfo']['currentPlayer'] != color:
            raise RuntimeError('KataGo side-to-move mismatch')
        move = policy_move(response, size) if mode == 'policy' else search_move(response)
        return move, {'request_id': str(self.number), 'mode': mode,
                      'raw_policy_move': policy_move(response, size), 'root': response['rootInfo'],
                      'top_search_moves': response['moveInfos'][:5],
                      'ms': (time.perf_counter() - started) * 1000}

    def close(self):
        try:
            self.outbound.put(None)
            self.writer.join(timeout=1)
            if self.writer.is_alive():
                self.proc.kill()
                self.proc.wait(timeout=3)
                self.writer.join(timeout=1)
            try:
                self.proc.stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=3)
        finally:
            self.reader.join(timeout=2)
            for stream in (self.proc.stdout, self.stderr, self.wire):
                try:
                    stream.close()
                except (BrokenPipeError, OSError, ValueError):
                    pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def config_text(time_ms):
    return f'''# Small, serial, fixed-orientation benchmark. No pondering.
logToStderr = true
numAnalysisThreads = 1
numSearchThreadsPerAnalysisThread = 1
nnMaxBatchSize = 1
nnCacheSizePowerOfTwo = 18
nnMutexPoolSizePowerOfTwo = 14
nnRandomize = false
rootNumSymmetriesToSample = 1
maxVisits = 10000000
maxTime = {time_ms / 1000}
wideRootNoise = 0
ignorePreRootHistory = false
conservativePass = false
preventCleanupPhase = false
useEvalCache = false
reportAnalysisWinratesAs = BLACK
'''


def engine(args):
    return GTP(args.exe, args.profile, size=19, nodes=10000000, depth=12,
               beam=12, search_mode='hybrid', time_ms=args.time_ms)


def fixtures(args, kata):
    rows = []
    with engine(args) as gp:
        for case in load_cases(args.fixtures):
            ref = setup(gp, case)
            # These are composed positions, not game records. Use setup stones
            # except for the ko fixture, where capture history is essential.
            preserve_history = case['family'] == 'immediate-ko'
            initial = None if preserve_history else [[c, vertex(i, 19)] for i, c in enumerate(ref.board) if c != '.']
            history = case['moves'] if preserve_history else []
            started = time.perf_counter()
            gp_report = gp.command(f"gp-search {case['color']}")
            gp_ms = (time.perf_counter() - started) * 1000
            gp_move = dict(f.split('=', 1) for f in gp_report.splitlines()[0].split())['move']
            for mode in ['policy', 'search']:
                move, trace = kata.choose(history, case['color'], 19, 0.5, mode, initial)
                check = copy.deepcopy(ref)
                check.play(case['color'], move)
                rows.append({'id': case['id'], 'mode': mode, 'move': move,
                             'position_input': 'full-history' if preserve_history else 'setup-stones',
                             'accepted': acceptable(case, move), 'trace': trace,
                             'hybrid_move': gp_move, 'hybrid_accepted': acceptable(case, gp_move),
                             'hybrid_ms': gp_ms, 'hybrid_trace': gp_report})
            print('fixture ' + case['id'], flush=True)
    return rows


def arena(args, kata):
    records = []
    rng = random.Random(args.seed)
    # One fixed generated two-move opening per pair, reused across all matches.
    openings = [rng.sample(['D4', 'Q4', 'D16', 'Q16'], 2) for _ in range(args.pairs)]
    for pair, points in enumerate(openings):
        opening = [['B', points[0]], ['W', points[1]]]
        for a, b in [('policy', 'hybrid'), ('search', 'hybrid'), ('search', 'policy')]:
            for a_color in ['B', 'W']:
                name = f'{pair}-{a}-vs-{b}-{a_color}'
                ref = Referee(19, args.komi)
                moves = copy.deepcopy(opening)
                decisions = []
                with engine(args) as gp:
                    gp.command(f'komi {args.komi}')
                    for color, move in opening:
                        ref.play(color, move)
                        gp.command(f'play {color} {move}')
                    with (args.output / (name + '.jsonl')).open('w', encoding='ascii') as transcript:
                        for turn in range(args.move_cap):
                            color = 'B' if turn % 2 == 0 else 'W'
                            role = a if color == a_color else b
                            started = time.perf_counter()
                            if role == 'hybrid':
                                move = gp.command(f'genmove {color}')
                                trace = {'report': gp.command('gp-last-search')}
                            else:
                                move, trace = kata.choose(moves, color, 19, args.komi, role)
                                gp.command(f'play {color} {move}')
                            elapsed = (time.perf_counter() - started) * 1000
                            ref.play(color, move)
                            ref.compare(gp.command('showboard'))
                            moves.append([color, move])
                            row = {'color': color, 'role': role, 'move': move, 'ms': elapsed, 'trace': trace}
                            decisions.append(row)
                            transcript.write(json.dumps(row) + '\n')
                            transcript.flush()
                            if ref.passes == 2:
                                break
                            if (turn + 1) % 100 == 0:
                                print(f'{name}: {turn + 1} moves', flush=True)
                    finished = ref.passes == 2
                    margin = ref.margin()
                    result = ('B' if margin > 0 else 'W') + f'+{abs(margin):g}' if margin else '0'
                    if finished and gp.command('final_score') != result:
                        raise RuntimeError('referee and goproverbs final score disagree')
                    (args.output / (name + '.sgf')).write_text(gp.command('gp-sgf'), encoding='ascii')
                winner_color = 'B' if margin > 0 else 'W' if margin < 0 else 'draw'
                record = {'pair': pair, 'a': a, 'b': b, 'a_color': a_color, 'opening': opening,
                          'finished': finished, 'result': result if finished else 'unfinished',
                          'winner': (a if winner_color == a_color else b) if finished and margin else None,
                          'moves': len(moves), 'raw_area_margin': margin,
                          'latency': {role: {'median_ms': statistics.median([d['ms'] for d in decisions if d['role'] == role]),
                                            'max_ms': max(d['ms'] for d in decisions if d['role'] == role)} for role in [a, b]}}
                records.append(record)
                (args.output / 'games.json').write_text(json.dumps(records, indent=2), encoding='ascii')
                print(f'{name}: {record["result"]}, winner={record["winner"]}', flush=True)
    return records


def hardware():
    result = {}
    for name, command in [('gpu', ['nvidia-smi', '--query-gpu=name,memory.used,memory.free,driver_version', '--format=csv']),
                          ('ollama', ['ollama', 'ps'])]:
        try:
            run = subprocess.run(command, capture_output=True, text=True, timeout=10,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            result[name] = {'stdout': run.stdout, 'stderr': run.stderr, 'exit_code': run.returncode}
        except (OSError, subprocess.TimeoutExpired) as exc:
            result[name] = {'error': str(exc)}
    try:
        import ctypes
        class Memory(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in ['total', 'available', 'page_total', 'page_available',
                                                      'virtual_total', 'virtual_available', 'extended']]
        memory = Memory()
        memory.length = ctypes.sizeof(memory)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            result['ram_bytes'] = {'total': memory.total, 'available': memory.available}
    except (AttributeError, OSError):
        pass
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('task', choices=['smoke', 'fixtures', 'arena'])
    p.add_argument('--katago', type=Path, required=True)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--exe', type=Path, default=ROOT / 'target/release/goproverbs.exe')
    p.add_argument('--profile', type=Path, default=ROOT / 'profiles/baseline.weights')
    p.add_argument('--fixtures', type=Path, default=ROOT / 'benchmarks/fixtures-19.json')
    p.add_argument('--time-ms', type=int, default=200)
    p.add_argument('--komi', type=float, default=7.5)
    p.add_argument('--pairs', type=int, default=1)
    p.add_argument('--seed', type=int, default=20260921)
    p.add_argument('--move-cap', type=int, default=722)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.time_ms < 1 or args.pairs < 1 or args.move_cap < 2:
        p.error('time, pairs and move cap must be positive (move cap >= 2)')
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    cfg = args.output / 'analysis.cfg'
    cfg.write_text(config_text(args.time_ms), encoding='ascii')
    manifest = {'status': 'running', 'settings': {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                'hashes': {k: digest(v) for k, v in {'katago': args.katago, 'model': args.model, 'goproverbs': args.exe,
                           'profile': args.profile, 'config': cfg, 'harness': Path(__file__), 'referee': ROOT / 'benchmarks/lab.py', 'fixtures': args.fixtures}.items()},
                'rules': 'tromp-taylor', 'board_size': 19,
                'policy_selection': 'raw policy argmax; one-visit retrieval, no searched values used',
                'search_selection': 'KataGo moveInfos order=0',
                'notes': 'Equal search time caps; actual elapsed measured. GPU neural vs CPU heuristic. No resignations. No cross-query search-tree reuse.'}
    def save():
        (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='ascii')
    save()
    try:
        manifest['hardware_before'] = hardware()
        for directory in ['round-20260920', 'overnight-20260916']:
            if (Path.home() / 'ai_bench' / directory / 'RUNNING.lock').exists():
                raise RuntimeError(f'Other inference runner owns {directory}; inspect before testing')
        resident = manifest['hardware_before'].get('ollama', {}).get('stdout', '').strip().splitlines()
        if len(resident) > 1:
            raise RuntimeError('Ollama model is resident; identify and unload idle workload before testing')
        with KataGo(args.katago.resolve(), args.model.resolve(), cfg, args.output) as kata:
            manifest['version'] = kata.request({'id': 'version', 'action': 'query_version'})
            manifest['warmup'] = kata.choose([], 'B', 19, args.komi, 'policy')
            manifest['hardware_loaded'] = hardware()
            if args.task == 'fixtures':
                manifest['fixtures'] = fixtures(args, kata)
            elif args.task == 'arena':
                manifest['games'] = arena(args, kata)
            else:
                manifest['search_smoke'] = kata.choose([], 'B', 19, args.komi, 'search')
            manifest['status'] = 'complete'
    except BaseException as exc:
        manifest['status'] = 'failed'
        manifest['error'] = repr(exc)
        raise
    finally:
        manifest['hardware_after'] = hardware()
        save()


if __name__ == '__main__':
    main()
