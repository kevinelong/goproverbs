import socket
import unittest
import time
from guidance import Broker, signed_value


class FakeKata:
    def request(self, query, deadline=None):
        self.query = query
        color = 'W' if query['moves'][-1][0] == 'B' else 'B'
        return {'rootInfo': {'currentPlayer': color, 'rawLead': 8.5}}


class GuidanceTests(unittest.TestCase):
    def test_black_white_perspective(self):
        self.assertEqual(signed_value({'rawLead': 8.5}, 'B'), 8.5)
        self.assertEqual(signed_value({'rawLead': 8.5}, 'W'), -8.5)
        with self.assertRaises(ValueError): signed_value({'rawLead': float('nan')}, 'B')

    def test_bridge_preserves_full_history_and_sends_one_visit(self):
        fake = FakeKata()
        with Broker(fake) as broker:
            with socket.create_connection(('127.0.0.1', broker.port)) as connection:
                connection.sendall(f'EVAL2 W {time.time_ns() // 1000 + 1000000} (;SZ[19]KM[7.5]RU[Tromp-Taylor];B[dd])\n'.encode())
                self.assertEqual(float(connection.makefile('rb').readline()), -8.5)
            self.assertEqual(fake.query['moves'], [['B', 'D16']])
            self.assertEqual(fake.query['maxVisits'], 1)
            self.assertEqual(broker.errors, [])

    def test_expired_queued_leaf_never_reaches_model(self):
        fake = FakeKata()
        with Broker(fake) as broker:
            with socket.create_connection(('127.0.0.1', broker.port), timeout=1) as connection:
                connection.sendall(b'EVAL2 W 1 (;SZ[19]KM[7.5]RU[Tromp-Taylor];B[dd])\n')
                self.assertEqual(connection.recv(64), b'')
            self.assertFalse(hasattr(fake, 'query'))
            self.assertEqual(broker.metrics['expired_before_query'], 1)
            self.assertEqual(broker.errors, [])

    def test_full_capture_pass_history_survives_bridge(self):
        # A ko capture followed by a pass: preserving only the final board
        # would lose the forbidden previous board. Colors are explicit SGF.
        from sgf_io import read_game, replay
        sgf = '(;SZ[5]KM[0.5]RU[Tromp-Taylor];B[ad];B[be];B[cd];W[bd];W[ac];W[cc];W[bb];B[bc];W[])'
        record = read_game(sgf)
        ref = replay(record)
        with self.assertRaisesRegex(AssertionError, 'superko'):
            ref.play('W', 'B2')
        fake = FakeKata()
        with Broker(fake) as broker:
            with socket.create_connection(('127.0.0.1', broker.port), timeout=1) as connection:
                connection.sendall(f'EVAL2 B {time.time_ns() // 1000 + 1000000} {sgf}\n'.encode())
                self.assertEqual(float(connection.makefile('rb').readline()), 8.5)
            self.assertEqual(fake.query['moves'], record['moves'])
            self.assertNotIn('initialStones', fake.query)
            self.assertEqual(fake.query['rules'], 'tromp-taylor')


if __name__ == '__main__': unittest.main()
