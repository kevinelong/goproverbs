import socket
import unittest
from guidance import Broker, signed_value


class FakeKata:
    def request(self, query):
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
                connection.sendall(b'EVAL W (;SZ[19]KM[7.5]RU[Tromp-Taylor];B[dd])\n')
                self.assertEqual(float(connection.makefile('rb').readline()), -8.5)
            self.assertEqual(fake.query['moves'], [['B', 'D16']])
            self.assertEqual(fake.query['maxVisits'], 1)
            self.assertEqual(broker.errors, [])


if __name__ == '__main__': unittest.main()
