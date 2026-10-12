"""Decision-path tests require no downloaded model or GPU."""
import unittest

from neural import make_query, policy_move, search_move, vertex


class NeuralTests(unittest.TestCase):
    def test_coordinates_and_pass(self):
        self.assertEqual(vertex(0, 19), 'A19')
        self.assertEqual(vertex(8, 19), 'J19')
        self.assertEqual(vertex(360, 19), 'T1')
        self.assertEqual(vertex(361, 19), 'pass')

    def test_policy_ignores_conflicting_searched_move(self):
        response = {'policy': [-1, 0.1, 0.2, 0.6, 0.1],
                    'moveInfos': [{'move': 'B2', 'order': 0, 'visits': 999}]}
        self.assertEqual(policy_move(response, 2), 'B1')
        self.assertEqual(search_move(response), 'B2')
        response['policy'] = [-1, 0.1, 0.1, 0.1, 0.7]
        self.assertEqual(policy_move(response, 2), 'pass')

    def test_malformed_policy_fails(self):
        for values in [[1], [-1] * 5, [float('nan')] * 5, [0] * 5]:
            with self.assertRaises(ValueError):
                policy_move({'policy': values}, 2)

    def test_history_rules_and_budget(self):
        moves = [['B', 'D4'], ['W', 'Q16']]
        query = make_query(1, moves, 'B', 19, 7.5, 'policy')
        self.assertEqual(query['moves'], moves)
        self.assertEqual(query['rules'], 'tromp-taylor')
        self.assertEqual(query['maxVisits'], 1)
        self.assertEqual(query['komi'], 7.5)
        self.assertNotIn('maxVisits', make_query(2, moves, 'B', 19, 7.5, 'search'))
        with self.assertRaises(ValueError):
            make_query(3, moves, 'W', 19, 7.5, 'policy')


if __name__ == '__main__':
    unittest.main()
