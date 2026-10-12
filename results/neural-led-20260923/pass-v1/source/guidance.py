"""Serial KataGo broker and optional guidance for the existing Rust hybrid."""
import json
import hashlib
import math
import socketserver
import threading
import time

from neural import make_query, vertex
from sgf_io import read_game


def signed_value(root, color):
    # KataGo config must report values as BLACK. rawLead is the raw neural
    # lead estimate, not searched scoreLead or a win probability.
    value = float(root['rawLead'])
    if not math.isfinite(value):
        raise ValueError('nonfinite neural lead')
    return value if color == 'B' else -value


class Broker:
    def __init__(self, kata):
        self.kata = kata
        self.lock = threading.Lock()
        self.count = 0
        self.errors = []
        self.metrics = {'leaf_requests': 0, 'expired_before_query': 0, 'timeouts': 0,
                        'completed': 0, 'queue_ms': 0.0, 'query_ms': 0.0, 'max_query_ms': 0.0,
                        'duplicate_histories': 0}
        self.histories = set()
        outer = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                try:
                    # Bound the entire admission read, including slow partial
                    # writes; a per-read timeout alone permits endless dripping.
                    admission = time.perf_counter() + 0.05
                    data = bytearray()
                    while b'\n' not in data:
                        left = admission - time.perf_counter()
                        if left <= 0:
                            raise TimeoutError('bridge admission deadline expired')
                        self.connection.settimeout(left)
                        chunk = self.connection.recv(8192)
                        if not chunk:
                            return
                        data.extend(chunk)
                        if len(data) > 131072:
                            raise ValueError('oversized evaluation request')
                    line = data.decode('ascii').strip()
                    command, color, expires, sgf = line.split(' ', 3)
                    if command != 'EVAL2' or color not in ['B', 'W']:
                        raise ValueError('bad evaluation request')
                    self.connection.settimeout(0.01)
                    remaining = int(expires) / 1_000_000 - time.time()
                    deadline = time.perf_counter() + min(remaining, 3600)
                    outer.metrics['leaf_requests'] += 1
                    if remaining <= 0:
                        outer.metrics['expired_before_query'] += 1
                        raise TimeoutError('leaf expired in broker queue')
                    record = read_game(sgf)
                    if record['rules'] != 'Tromp-Taylor':
                        raise ValueError('neural evaluation requires TT rules')
                    response = outer.query(record['moves'], color, record['size'], record['komi'], deadline=deadline)
                    value = signed_value(response['rootInfo'], color)
                    self.wfile.write(f'{value:.12g}\n'.encode('ascii'))
                except TimeoutError:
                    # Budget exhaustion is expected fallback, not a protocol error.
                    pass
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    # A Rust search can abandon this leaf at its deadline.
                    pass
                except Exception as exc:
                    outer.errors.append(repr(exc))
                    try: self.wfile.write(b'error\n')
                    except OSError: pass

        self.server = socketserver.TCPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
        self.thread.start()

    @property
    def port(self):
        return self.server.server_address[1]

    def query(self, moves, color, size, komi, deadline=None):
        deadline = time.perf_counter() + 180 if deadline is None else deadline
        start = time.perf_counter()
        if not self.lock.acquire(timeout=max(0, deadline - start)):
            self.metrics['timeouts'] += 1
            raise TimeoutError('broker lock deadline expired')
        self.metrics['queue_ms'] += (time.perf_counter() - start) * 1000
        try:
            if time.perf_counter() >= deadline:
                self.metrics['expired_before_query'] += 1
                raise TimeoutError('broker request expired before query')
            self.count += 1
            query = make_query(f'broker-{self.count}', moves, color, size, komi, 'policy')
            key = hashlib.sha256(json.dumps([moves, color, size, komi, 'tromp-taylor']).encode('ascii')).digest()
            self.metrics['duplicate_histories'] += key in self.histories
            self.histories.add(key)
            response = self.kata.request(query, deadline=deadline)
            if time.perf_counter() >= deadline:
                raise TimeoutError('broker result arrived late')
            self.metrics['completed'] += 1
        except TimeoutError:
            self.metrics['timeouts'] += 1
            raise
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            self.metrics['query_ms'] += elapsed
            self.metrics['max_query_ms'] = max(self.metrics['max_query_ms'], elapsed)
            self.lock.release()
        if response['rootInfo']['currentPlayer'] != color:
            raise RuntimeError('neural player perspective mismatch')
        return response

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=10)

    def __enter__(self): return self
    def __exit__(self, *_): self.close()


def choose(gp, broker, moves, color, komi, mode, time_ms, top_k=3):
    if mode not in ['HH', 'NH', 'HN', 'NN']:
        raise ValueError('guidance mode must be HH/NH/HN/NN')
    start = time.perf_counter()
    deadline = time.perf_counter() + time_ms / 1000
    hints = []
    root_timeout = False
    if mode[0] == 'N':
        try:
            response = broker.query(moves, color, 19, komi, deadline=deadline)
            values = response['policy']
            indices = sorted((i for i, p in enumerate(values) if p >= 0), key=lambda i: -values[i])[:top_k]
            hints = [vertex(i, 19) for i in indices]
        except TimeoutError:
            root_timeout = True
    gp.command('gp-nominees ' + (','.join(hints) if hints else '-'))
    gp.command(f'gp-neural-port {broker.port if mode[1] == "N" else 0}')
    remaining = max(0, int(time_ms - (time.perf_counter() - start) * 1000))
    gp.command(f'gp-limits {remaining} 10000000 12 12')
    move = gp.command(f'genmove {color}')
    report = gp.command('gp-last-search')
    if broker.errors:
        raise RuntimeError(f'neural broker failed: {broker.errors[-1]}')
    return move, {'mode': mode, 'hints': hints, 'remaining_search_ms': remaining,
                  'root_timeout': root_timeout,
                  'ms': (time.perf_counter() - start) * 1000, 'report': report}
