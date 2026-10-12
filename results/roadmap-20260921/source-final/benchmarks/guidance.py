"""Serial KataGo broker and optional guidance for the existing Rust hybrid."""
import json
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
        outer = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(5)
                try:
                    line = self.rfile.readline(131072).decode('ascii').strip()
                    command, color, sgf = line.split(' ', 2)
                    if command != 'EVAL' or color not in ['B', 'W']:
                        raise ValueError('bad evaluation request')
                    record = read_game(sgf)
                    if record['rules'] != 'Tromp-Taylor':
                        raise ValueError('neural evaluation requires TT rules')
                    response = outer.query(record['moves'], color, record['size'], record['komi'])
                    value = signed_value(response['rootInfo'], color)
                    self.wfile.write(f'{value:.12g}\n'.encode('ascii'))
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

    def query(self, moves, color, size, komi):
        with self.lock:
            self.count += 1
            response = self.kata.request(make_query(f'broker-{self.count}', moves, color, size, komi, 'policy'))
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
    hints = []
    if mode[0] == 'N':
        response = broker.query(moves, color, 19, komi)
        values = response['policy']
        indices = sorted((i for i, p in enumerate(values) if p >= 0), key=lambda i: -values[i])[:top_k]
        hints = [vertex(i, 19) for i in indices]
    gp.command('gp-nominees ' + (','.join(hints) if hints else '-'))
    gp.command(f'gp-neural-port {broker.port if mode[1] == "N" else 0}')
    remaining = max(0, int(time_ms - (time.perf_counter() - start) * 1000))
    gp.command(f'gp-limits {remaining} 10000000 12 12')
    move = gp.command(f'genmove {color}')
    report = gp.command('gp-last-search')
    return move, {'mode': mode, 'hints': hints, 'remaining_search_ms': remaining,
                  'ms': (time.perf_counter() - start) * 1000, 'report': report}
