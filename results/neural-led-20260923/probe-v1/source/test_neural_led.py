"""Deterministic decision controls: no model, sockets, or background workers."""
import copy
import unittest
from unittest.mock import patch

from neural import vertex
from neural_led import DecisionError, choose


class Clock:
    def __init__(self):
        self.now = 10.0

    def __call__(self):
        return self.now


class FakeKata:
    def __init__(self, clock, root=None, values=None, costs=None, fail_at=None, change=None):
        self.clock, self.root, self.values = clock, root, values or {}
        self.costs, self.fail_at, self.change = costs or [], fail_at, change
        self.queries = []

    def request(self, query, deadline=None):
        index = len(self.queries)
        self.queries.append((copy.deepcopy(query), deadline))
        self.clock.now += self.costs[index] if index < len(self.costs) else 0.001
        if self.fail_at is not None and index == self.fail_at[0]:
            raise self.fail_at[1]
        player = ('W' if query['moves'][-1][0] == 'B' else 'B') if query['moves'] else query['initialPlayer']
        root = {'currentPlayer': player, 'winrate': 0.5, 'scoreLead': 0.0}
        if index == 0:
            size = query['boardXSize']
            policy = self.root if self.root is not None else [0.5, 0.3, 0.2] + [0.] * (size * size - 2)
            result = {'id': query['id'], 'rootInfo': root, 'policy': policy}
        else:
            value = self.values.get(query['moves'][-1][1], 0.5)
            if isinstance(value, dict):
                root = copy.deepcopy(value)
            else:
                root['winrate'] = value
            result = {'id': query['id'], 'rootInfo': root}
        if self.change:
            self.change(index, result)
        return result


def policy(size, *moves):
    result = [-1.] * (size * size + 1)
    vertices = [vertex(i, size) for i in range(size * size + 1)]
    for i, move in enumerate(moves):
        result[vertices.index(move)] = 1 / (i + 2)
    return result


class NeuralLedTests(unittest.TestCase):
    def run_choice(self, color='B', variant='neural', history=None, size=3, komi=.5,
                   proposer=None, time_ms=100, cancelled=None, **kwargs):
        clock = Clock()
        kata = FakeKata(clock, **kwargs)
        result = choose(kata, history or [], color, size, komi, time_ms,
                        variant=variant, proposer=proposer, clock=clock, cancelled=cancelled)
        return result, kata

    def test_policy_never_uses_searched_move_or_requests_children(self):
        (move, trace), kata = self.run_choice(variant='policy', change=lambda i, r:
                                            r.update(moveInfos=[{'move': 'pass', 'order': 0}]))
        self.assertEqual(move, 'A3')
        self.assertEqual(len(kata.queries), 1)
        self.assertEqual(trace['completed_rounds'], 0)
        self.assertEqual(trace['status'], 'policy')

    def test_black_and_white_maximize_own_not_opponent_winrate(self):
        values = {'A3': .2, 'B3': .8, 'C3': .6}
        for color, expected in [('B', 'B3'), ('W', 'A3')]:
            (move, trace), kata = self.run_choice(color=color, values=values)
            self.assertEqual(move, expected)
            self.assertEqual(trace['completed_rounds'], 1)
            self.assertFalse(trace['fallback'])
            self.assertEqual(len(kata.queries), 4)

    def test_complete_round_or_root_even_if_partial_challenger_looks_better(self):
        (move, trace), kata = self.run_choice(values={'A3': .1, 'B3': .9},
                                             fail_at=(3, TimeoutError('cancel submitted')))
        self.assertEqual(move, 'A3')
        self.assertEqual(trace['completed_rounds'], 0)
        self.assertTrue(trace['fallback'])
        self.assertEqual([r['status'] for r in trace['candidates']],
                         ['evaluated', 'evaluated', 'unevaluated'])
        self.assertEqual(trace['candidates'][1]['value']['winrate'], .9)
        self.assertEqual(trace['queries'][-1]['status'], 'timeout')
        self.assertEqual(len(kata.queries), 4)  # No retry after transport-owned cancellation.

    def test_late_child_response_kept_only_as_telemetry(self):
        (move, trace), kata = self.run_choice(costs=[.001, .001, .2], values={'B3': 1})
        self.assertEqual(move, 'A3')
        self.assertEqual(trace['queries'][-1]['status'], 'late')
        self.assertEqual(trace['queries'][-1]['rootInfo']['winrate'], 1)
        self.assertNotIn('value', trace['candidates'][1])
        self.assertGreater(trace['overshoot_ms'], 0)
        self.assertEqual(len(kata.queries), 3)

    def test_root_timeout_or_late_is_failed_decision_not_heuristic_fallback(self):
        for kwargs in [{'costs': [.101]}, {'fail_at': (0, TimeoutError('root timeout'))}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(DecisionError) as caught:
                self.run_choice(**kwargs)
            trace = caught.exception.trace
            self.assertEqual(trace['status'], 'failed')
            self.assertEqual(trace['failure_kind'], 'root_unavailable')
            self.assertIsNone(trace['selected_move'])

    def test_expired_during_replay_never_submits_root(self):
        from lab import Referee
        clock = Clock()
        kata = FakeKata(clock)
        play = Referee.play
        def slow_play(ref, color, move):
            clock.now += .101
            play(ref, color, move)
        with patch.object(Referee, 'play', slow_play), self.assertRaises(DecisionError):
            choose(kata, [['W', 'A1']], 'B', 3, .5, 100, clock=clock)
        self.assertEqual(kata.queries, [])

    def test_expired_during_query_construction_never_submits(self):
        from neural import make_query
        clock = Clock()
        kata = FakeKata(clock)
        def slow_query(*args, **kwargs):
            clock.now += .101
            return make_query(*args, **kwargs)
        with patch('neural_led.make_query', slow_query), self.assertRaises(DecisionError):
            choose(kata, [], 'B', 3, .5, 100, clock=clock)
        self.assertEqual(kata.queries, [])

    def test_final_selection_boundary_rejects_expired_round(self):
        clock = Clock()
        kata = FakeKata(clock, values={'B3': .9})
        def clock_at_final_selection():
            # Once the last child is returned, five clock reads perform query
            # checks/timing, child and round checks, then final finish. Expire
            # precisely at the final boundary rather than at response receipt.
            if len(kata.queries) == 4:
                clock_at_final_selection.reads += 1
                if clock_at_final_selection.reads == 5:
                    clock.now += .2
            return clock()
        clock_at_final_selection.reads = 0
        move, trace = choose(kata, [], 'B', 3, .5, 100, clock=clock_at_final_selection)
        self.assertEqual(move, 'A3')
        self.assertEqual(trace['completed_rounds'], 0)
        self.assertEqual(trace['fallback_reason'], 'deadline')
        self.assertEqual(len([r for r in trace['candidates'] if 'value' in r]), 3)

    def test_operational_errors_do_not_become_ordinary_fallback(self):
        for failure in [RuntimeError('transport died'), ValueError('bad response')]:
            with self.subTest(failure=failure), self.assertRaises(DecisionError) as caught:
                self.run_choice(fail_at=(2, failure))
            self.assertEqual(caught.exception.trace['failure_kind'], 'operational')
            self.assertEqual(caught.exception.trace['root_move'], 'A3')
            self.assertIsNone(caught.exception.trace['selected_move'])

    def test_missing_nonfinite_out_of_range_and_wrong_perspective_are_invalid(self):
        for value in [{'currentPlayer': 'W'}, {'currentPlayer': 'B', 'winrate': .7},
                      {'currentPlayer': 'W', 'winrate': float('nan')},
                      {'currentPlayer': 'W', 'winrate': 1.1},
                      {'currentPlayer': 'W', 'winrate': True},
                      {'currentPlayer': 'W', 'winrate': .5, 'scoreLead': float('inf')}]:
            with self.subTest(value=value), self.assertRaises(DecisionError):
                self.run_choice(values={'A3': value})

    def test_score_tiebreak_normalizes_white_and_missing_score_disables_globally(self):
        values = {'A3': {'currentPlayer': 'B', 'winrate': .5, 'scoreLead': 3},
                  'B3': {'currentPlayer': 'B', 'winrate': .5, 'scoreLead': -4},
                  'C3': {'currentPlayer': 'B', 'winrate': .5, 'scoreLead': 1}}
        (move, trace), _ = self.run_choice(color='W', values=values)
        self.assertEqual(move, 'B3')
        self.assertTrue(trace['score_tiebreak_used'])
        del values['C3']['scoreLead']
        (move, trace), _ = self.run_choice(color='W', values=values)
        self.assertEqual(move, 'A3')
        self.assertFalse(trace['score_tiebreak_used'])

    def test_nominees_deduplicate_filter_and_cap_per_specialist(self):
        def proposer(**kwargs):
            self.assertEqual(kwargs['variant'], 'combined')
            self.assertGreater(kwargs['deadline'], 10)
            return {'heuristic': ['A3', 'A3', 'bad', 'A1', 'B1', 'C1'],
                    'tactical': ['B1', 'pass', 'C2', 'A2'], 'metadata': {'proof': False}}
        (move, trace), _ = self.run_choice(variant='combined', proposer=proposer,
                                          values={'pass': .9})
        self.assertEqual(move, 'pass')
        self.assertEqual([r['move'] for r in trace['candidates']],
                         ['A3', 'B3', 'C3', 'A1', 'B1', 'pass', 'C2'])
        self.assertEqual(trace['candidates'][0]['sources'], ['neural', 'heuristic'])
        self.assertEqual(trace['candidates'][4]['sources'], ['heuristic', 'tactical'])
        self.assertEqual(len(trace['rejected']), 1)
        self.assertEqual(trace['proposals']['metadata'], {'proof': False})

    def test_full_history_superko_rejects_recapture(self):
        history = [['B', 'A2'], ['B', 'B1'], ['B', 'C2'], ['W', 'B2'],
                   ['W', 'A3'], ['W', 'C3'], ['W', 'B4'], ['B', 'B3']]
        original = copy.deepcopy(history)
        (move, trace), kata = self.run_choice(color='W', size=5, history=history,
            root=policy(5, 'A5', 'D5', 'E5'), variant='tactical',
            proposer=lambda **kw: {'tactical': ['B2', 'A2', 'pass']})
        self.assertEqual(history, original)
        self.assertTrue(any('superko' in r['reason'] for r in trace['rejected']))
        self.assertTrue(any('occupied' in r['reason'] for r in trace['rejected']))
        for query, deadline in kata.queries:
            self.assertEqual(query['moves'][:len(history)], history)
            self.assertEqual(query['komi'], .5)
            self.assertEqual(query['rules'], 'tromp-taylor')
            self.assertEqual(query['maxVisits'], 1)
            self.assertNotIn('initialStones', query)
            self.assertEqual(deadline, 10.1)

    def test_proposer_cannot_mutate_callers_history_or_queries(self):
        history = [['B', 'A1']]
        def proposer(**kwargs):
            kwargs['moves'][0][1] = 'B1'
            return {'heuristic': ['pass']}
        (_, _), kata = self.run_choice(color='W', history=history, variant='heuristic', proposer=proposer)
        self.assertEqual(history, [['B', 'A1']])
        self.assertTrue(all(q['moves'][0] == ['B', 'A1'] for q, _ in kata.queries))

    def test_exact_two_pass_child_uses_referee_not_model(self):
        for color, komi, expected in [('W', .5, 1), ('B', .5, 0), ('B', 0, .5)]:
            other = 'B' if color == 'W' else 'W'
            (move, trace), kata = self.run_choice(color=color, komi=komi,
                history=[[other, 'pass']], root=policy(3, 'pass'))
            self.assertEqual(move, 'pass')
            self.assertEqual(len(kata.queries), 1)
            self.assertTrue(trace['candidates'][0]['value']['exact'])
            self.assertEqual(trace['candidates'][0]['value']['winrate'], expected)
            self.assertEqual(trace['completed_rounds'], 1)

    def test_terminal_root_never_queries(self):
        (move, trace), kata = self.run_choice(history=[['B', 'pass'], ['W', 'pass']])
        self.assertIsNone(move)
        self.assertEqual(trace['status'], 'terminal')
        self.assertEqual(trace['terminal']['score'], -.5)
        self.assertEqual(kata.queries, [])

    def test_cancelled_before_root_fails_without_query(self):
        clock = Clock()
        kata = FakeKata(clock)
        with self.assertRaises(DecisionError) as caught:
            choose(kata, [], 'B', 3, .5, 100, clock=clock, cancelled=lambda: True)
        self.assertEqual(kata.queries, [])
        self.assertEqual(caught.exception.trace['failure_kind'], 'root_unavailable')

    def test_cancellation_after_root_retains_root_and_starts_no_new_work(self):
        cancelled = [False]
        def proposer(**kwargs):
            cancelled[0] = True
            return {'heuristic': ['A1']}
        (move, trace), kata = self.run_choice(variant='heuristic', proposer=proposer,
                                            cancelled=lambda: cancelled[0])
        self.assertEqual(move, 'A3')
        self.assertEqual(trace['fallback_reason'], 'cancelled')
        self.assertEqual(len(kata.queries), 1)

    def test_nomination_overrun_is_measured_and_never_evaluated(self):
        clock = Clock()
        kata = FakeKata(clock)
        def proposer(**kwargs):
            clock.now += .2
            return {'heuristic': ['A1']}
        move, trace = choose(kata, [], 'B', 3, .5, 100, 'heuristic', proposer, clock=clock)
        self.assertEqual(move, 'A3')
        self.assertEqual(len(kata.queries), 1)
        self.assertGreater(trace['overshoot_ms'], 100)
        self.assertAlmostEqual(trace['nomination_ms'], 200)

    def test_invalid_policy_and_illegal_favorite_fail(self):
        cases = [[0] * 10, [1], [float('nan')] * 10, [-.5] * 10, [True] * 10]
        for root in cases:
            with self.subTest(root=root), self.assertRaises(DecisionError):
                self.run_choice(root=root)
        with self.assertRaises(DecisionError):
            self.run_choice(color='W', history=[['B', 'A3']])

    def test_intermediate_wrong_id_and_wrong_root_player_fail(self):
        for changes in [{'isDuringSearch': True}, {'_used_intermediate': True},
                        {'id': 'wrong'}, {'rootInfo': {'currentPlayer': 'W'}}]:
            with self.subTest(changes=changes), self.assertRaises(DecisionError):
                self.run_choice(change=lambda i, r: r.update(changes))

    def test_invalid_inputs_and_missing_proposer_fail(self):
        for args in [{'color': 'X'}, {'time_ms': 0}, {'time_ms': float('inf')},
                     {'size': True}, {'komi': float('nan')}, {'variant': 'unknown'},
                     {'variant': 'heuristic'}, {'history': [['B', 'A0']]},
                     {'history': [['B', 'pass']]},
                     {'history': [['B', 'pass'], ['W', 'pass'], ['B', 'A1']]}]:
            with self.subTest(args=args), self.assertRaises(DecisionError):
                self.run_choice(**args)


if __name__ == '__main__':
    unittest.main()
