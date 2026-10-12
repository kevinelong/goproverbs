"""Screen controls that protect pair identity and stopping decisions."""
import unittest

from lab import Referee
from neural_led_screen import canonical, fresh_openings, pair_gate, schedule


class ScreenTests(unittest.TestCase):
    def test_freshness_symmetry_legality_and_repeatability(self):
        excluded = {canonical([['B', 'D4'], ['W', 'Q16'], ['B', 'D16'], ['W', 'Q4']])}
        rows = fresh_openings(excluded)
        self.assertEqual(rows, fresh_openings(excluded))
        keys = {canonical(r['moves']) for r in rows}
        self.assertEqual(len(keys), 40)
        self.assertFalse(keys & excluded)
        for row in rows:
            ref = Referee(19, 7.5)
            for color, move in row['moves']:
                ref.play(color, move)
            self.assertEqual(ref.board.count('B'), 2)
            self.assertEqual(ref.board.count('W'), 2)
        self.assertEqual(canonical([['B', 'D4'], ['W', 'Q16']]),
                         canonical([['B', 'Q4'], ['W', 'D16']]))
        self.assertNotEqual(canonical([['B', 'D4'], ['W', 'Q16']]),
                            canonical([['W', 'D4'], ['B', 'Q16']]))

    def test_two_separate_stages_preserve_complete_adjacent_pairs(self):
        rows = schedule(fresh_openings(set()))
        self.assertEqual(len(rows), 80)
        self.assertEqual([r['stage'] for r in rows], [1]*40+[2]*40)
        first = {r['opening']['id'] for r in rows[:40]}
        second = {r['opening']['id'] for r in rows[40:]}
        self.assertFalse(first & second)
        for i in range(0, 80, 2):
            a, b = rows[i:i+2]
            self.assertEqual(a['opening'], b['opening'])
            self.assertEqual({a['a_color'], b['a_color']}, {'B', 'W'})
            self.assertNotEqual(a['stem'], b['stem'])

    def test_pair_gate_retention_and_jitter_not_wins(self):
        def game(complete=80, late=1):
            return {'roles': {'neural': {'decisions':100, 'complete_rounds':complete, 'over_205':late},
                              'policy': {'decisions':100, 'complete_rounds':0, 'over_205':0}}}
        pair_gate([game(), game()])
        with self.assertRaisesRegex(RuntimeError, '80%'):
            pair_gate([game(79), game(79)])
        with self.assertRaisesRegex(RuntimeError, '1%'):
            pair_gate([game(late=2), game(late=1)])


if __name__ == '__main__':
    unittest.main()
