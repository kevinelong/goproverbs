import time
import unittest
from unittest.mock import Mock
from neural_led_probe import Proposer, parse_candidates, parse_tactical, schedule


class ProbeControls(unittest.TestCase):
    def test_schedule_balanced_reproducible(self):
        cases=[{'id':str(i)} for i in range(8)]
        rows=schedule(cases)
        self.assertEqual(rows,schedule(cases))
        self.assertEqual(len(rows),80)
        self.assertEqual(len({tuple(r.values()) for r in rows}),80)

    def test_parsers_and_depth_comparability(self):
        self.assertEqual(parse_candidates('D4 3.2 capture:1\npass 0.0')[0]['move'],'D4')
        with self.assertRaises(ValueError): parse_candidates('D4 nan')
        text='move=D4 score=2\n  C3 heuristic=0 scout=1 verified=100 depth=1\n  Q4 heuristic=0 scout=1 verified=3 depth=2\n  D4 heuristic=0 scout=1 verified=4 depth=2'
        self.assertEqual(parse_tactical(text),['D4','Q4'])
        self.assertEqual(parse_tactical('move=pass score=0'),['pass'])

    def test_nomination_deadline_kills_only_its_gtp(self):
        gp=Mock()
        gp.command.side_effect=lambda _:time.sleep(.08)
        proposer=Proposer(gp,[])
        with self.assertRaises(TimeoutError):
            proposer.command('gp-candidates B',time.perf_counter()+.01)
        self.assertTrue(proposer.poisoned)
        gp.proc.kill.assert_called_once()
        for thread in proposer.threads: thread.join(timeout=1)
        with self.assertRaises(RuntimeError):
            proposer.command('showboard',time.perf_counter()+1)


if __name__=='__main__': unittest.main()
