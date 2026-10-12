"""Pure direct-arena tests; no executable, model, or GPU is used."""
import json
from pathlib import Path
import tempfile
import unittest

from direct_arena import (MATCHUPS, build_schedule, legal_fallback, load_openings,
                          paired_summary, role_for_color, standalone_decision)
from lab import Referee


class FakeKata:
    def __init__(self, response=None, timeout=False):
        self.response = response
        self.timeout = timeout
        self.queries = []

    def request(self, query, deadline=None, allow_partial=False):
        self.queries.append((query, deadline))
        if self.timeout:
            raise TimeoutError('synthetic timeout')
        return self.response


class DirectArenaTests(unittest.TestCase):
    def opening_file(self, openings):
        temporary = tempfile.TemporaryDirectory()
        path = Path(temporary.name) / 'openings.json'
        path.write_text(json.dumps({'openings': openings}), encoding='ascii')
        self.addCleanup(temporary.cleanup)
        return path

    def test_exact_opening_count_and_legality(self):
        rows = [{'id': 'one', 'moves': [['B', 'D4'], ['W', 'Q16']]},
                {'id': 'two', 'moves': [['B', 'Q4'], ['W', 'D16']]}]
        self.assertEqual(load_openings(self.opening_file(rows), 2), rows)
        with self.assertRaisesRegex(ValueError, 'exactly 1'):
            load_openings(self.opening_file(rows), 1)
        rows[1]['id'] = 'one'
        with self.assertRaisesRegex(ValueError, 'unique'):
            load_openings(self.opening_file(rows), 2)

    def test_pairing_and_color_roles(self):
        opening = {'id': 'fixed', 'moves': []}
        schedule = build_schedule([opening])
        self.assertEqual(len(schedule), 2 * len(MATCHUPS))
        self.assertEqual({(g['a'], g['b']) for g in schedule}, set(MATCHUPS))
        for game in schedule:
            self.assertEqual(role_for_color(game, game['a_color']), game['a'])
            other = 'W' if game['a_color'] == 'B' else 'B'
            self.assertEqual(role_for_color(game, other), game['b'])

    def test_policy_selection_ignores_search_and_search_budget_is_reserved(self):
        policy = [-1.0] * 362
        policy[0] = 0.7
        policy[1] = 0.2
        response = {'policy': policy, 'rootInfo': {'currentPlayer': 'B'},
                    'moveInfos': [{'move': 'Q16', 'order': 0}]}
        kata = FakeKata(response)
        ref = Referee(19, 7.5)
        move, trace = standalone_decision(kata, ref, [], 'B', 'policy', 200, 'p')
        self.assertEqual(move, 'A19')
        self.assertFalse(trace['fallback'])
        self.assertEqual(kata.queries[-1][0]['maxVisits'], 1)
        move, _ = standalone_decision(kata, ref, [], 'B', 'search', 200, 's')
        self.assertEqual(move, 'Q16')
        self.assertEqual(kata.queries[-1][0]['overrideSettings']['maxTime'], 0.19)

    def test_timeout_without_answer_stops_instead_of_inventing_weak_move(self):
        ref = Referee(19, 7.5)
        ref.play('B', 'A19')
        kata = FakeKata(timeout=True)
        with self.assertRaisesRegex(RuntimeError, 'no timely answer'):
            standalone_decision(kata, ref, [['B', 'A19']], 'W', 'policy', 200, 'timeout')

    def test_pair_summary_treats_opening_as_unit(self):
        games = []
        for a, b in MATCHUPS:
            for color, won in [('B', True), ('W', False)]:
                games.append({'opening': 'o', 'matchup': f'{a}-vs-{b}',
                              'a_color': color, 'finished': True,
                              'result': 'B+1', 'a_won': won})
        result = paired_summary(games)
        for row in result['matchups'].values():
            self.assertEqual(row['complete_pairs'], 1)
            self.assertEqual(row['mean_pair_score_for_a'], 0.5)


if __name__ == '__main__':
    unittest.main()
