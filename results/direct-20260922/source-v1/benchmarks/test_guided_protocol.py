import unittest
from lab import GTP, ROOT


class GuidedProtocolTests(unittest.TestCase):
    def test_hints_clear_after_move_and_invalid_input_is_atomic(self):
        with GTP(ROOT/'target/release/goproverbs.exe',size=5,search_mode='hybrid',depth=2,nodes=100000,time_ms=1000) as gp:
            gp.command('gp-nominees E5,E5')
            with self.assertRaises(RuntimeError): gp.command('gp-nominees E5,not-a-point')
            report=gp.command('gp-search B')
            lines=[s for s in report.splitlines() if s.startswith('  E5 ')]
            self.assertEqual(len(lines),1)
            self.assertIn('neural_hint=true',lines[0])
            gp.command('play B A1')
            self.assertNotIn('neural_hint=true',gp.command('gp-search W'))

    def test_missing_external_server_falls_back_to_complete_scout(self):
        import socket
        # Reserve an unlistened port to ensure a connection cannot be accepted.
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1',0))
            with GTP(ROOT/'target/release/goproverbs.exe',size=5,search_mode='hybrid',depth=2,nodes=100000,time_ms=1000) as gp:
                gp.command(f'gp-neural-port {reserved.getsockname()[1]}')
                report=gp.command('gp-search B')
                self.assertIn('depth=1 ',report)
                self.assertIn('limited=true',report)
                self.assertIn('external_leaf=false',report)


if __name__=='__main__': unittest.main()
