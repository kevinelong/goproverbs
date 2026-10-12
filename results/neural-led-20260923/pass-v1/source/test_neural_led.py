"""Deterministic decision controls: no model, sockets, or background workers."""
import copy
import unittest
from unittest.mock import patch

from lab import Referee
from neural import vertex
from neural_led import DecisionError, _child, choose


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


class RefereeBranchTests(unittest.TestCase):
    def test_long_history_children_match_deepcopy_reference(self):
        ref = Referee(19, 7.5)
        # A connected Black region retains liberties while accumulating 287
        # distinct legal board states, reproducing the costly history length.
        for index in range(287):
            ref.play('B', vertex(index, 19))
        root = copy.deepcopy(ref)
        self.assertEqual(len(ref.seen), 288)
        for color, move in [('B', 'C4'), ('W', 'T1'), ('B', 'A1'),
                            ('W', 'pass'), ('B', 'A19')]:
            with self.subTest(color=color, move=move):
                reference = copy.deepcopy(ref)
                try:
                    reference.play(color, move)
                except AssertionError as expected:
                    with self.assertRaises(AssertionError) as actual:
                        _child(ref, color, move)
                    self.assertEqual(str(actual.exception), str(expected))
                else:
                    branch = _child(ref, color, move)
                    self.assertEqual(vars(branch), vars(reference))
                    self.assertEqual(branch.margin(), reference.margin())
                self.assertEqual(vars(ref), vars(root))

    def test_sibling_board_history_and_passes_are_isolated(self):
        ref = Referee(5, 6.5)
        ref.play('B', 'C3')
        root = copy.deepcopy(ref)
        left = _child(ref, 'W', 'A1')
        right = _child(ref, 'W', 'E5')
        right_before = copy.deepcopy(right)
        left.play('B', 'pass')
        left.play('W', 'A2')
        self.assertEqual(vars(ref), vars(root))
        self.assertEqual(vars(right), vars(right_before))
        self.assertNotIn(tuple(left.board), ref.seen)
        self.assertNotIn(tuple(left.board), right.seen)
        # Mutation of the containers themselves must not cross branches either.
        left.board[0] = 'B'
        left.seen.clear()
        self.assertEqual(vars(ref), vars(root))
        self.assertEqual(vars(right), vars(right_before))

    def test_capture_branch_retains_superko_without_poisoning_siblings(self):
        ref = Referee(5, .5)
        for color, move in [('B', 'A2'), ('B', 'B1'), ('B', 'C2'),
                            ('W', 'B2'), ('W', 'A3'), ('W', 'C3'), ('W', 'B4')]:
            ref.play(color, move)
        root = copy.deepcopy(ref)
        captured = _child(ref, 'B', 'B3')
        reference = copy.deepcopy(ref)
        reference.play('B', 'B3')
        self.assertEqual(vars(captured), vars(reference))
        self.assertEqual(captured.board[(5-2)*5+1], '.')
        before_recapture = copy.deepcopy(captured)
        with self.assertRaisesRegex(AssertionError, 'superko'):
            _child(captured, 'W', 'B2')
        self.assertEqual(vars(captured), vars(before_recapture))
        passed = _child(captured, 'B', 'pass')
        with self.assertRaisesRegex(AssertionError, 'superko'):
            _child(passed, 'W', 'B2')
        self.assertEqual(vars(_child(ref, 'B', 'B3')), vars(reference))
        self.assertEqual(vars(ref), vars(root))

    def test_pass_child_preserves_exact_scoring_state_and_full_history(self):
        ref = Referee(5, 7.5)
        ref.play('B', 'C3')
        ref.play('W', 'A1')
        ref.play('B', 'pass')
        root = copy.deepcopy(ref)
        terminal = _child(ref, 'W', 'pass')
        expected = copy.deepcopy(ref)
        expected.play('W', 'pass')
        self.assertEqual(vars(terminal), vars(expected))
        self.assertEqual(terminal.passes, 2)
        self.assertEqual(terminal.margin(), ref.margin())
        terminal.board[0] = 'W'
        terminal.seen.clear()
        self.assertEqual(vars(ref), vars(root))


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

    def test_pass_agreement_winning_losing_drawn_both_colors_all_evaluated_roles(self):
        for color in ('B', 'W'):
            for komi in (-.5, 0, .5):
                for variant in ('neural', 'heuristic', 'tactical', 'combined'):
                    other = 'B' if color == 'W' else 'W'
                    def forbidden(**kwargs):
                        self.fail('Pass agreement must not request specialist proposals')
                    (move, trace), kata = self.run_choice(color=color, komi=komi,
                        history=[[other, 'pass']], root=policy(3, 'pass', 'A3', 'B3'),
                        variant=variant, proposer=forbidden)
                    score = -komi if color == 'B' else komi
                    self.assertEqual(move, 'pass')
                    self.assertEqual(len(kata.queries), 1)
                    self.assertTrue(trace['pass_agreement'])
                    self.assertFalse(trace['fallback'])
                    self.assertEqual(trace['status'], 'pass_agreement')
                    self.assertEqual(trace['agreed_terminal']['score'], score)
                    self.assertEqual(trace['agreed_terminal']['winrate'], 1 if score>0 else 0 if score<0 else .5)
                    self.assertEqual(trace['completed_rounds'], 0)
                    self.assertEqual(trace['candidates'], [])

    def test_opponent_pass_alone_does_not_force_acceptance(self):
        for color in ('B', 'W'):
            other = 'W' if color == 'B' else 'B'
            (move, trace), kata = self.run_choice(color=color, history=[[other, 'pass']],
                root=policy(3, 'A3', 'pass'), komi=.5 if color=='B' else -.5,
                values={'A3': .8 if color=='B' else .2})
            self.assertEqual(move, 'A3')
            self.assertFalse(trace['pass_agreement'])
            self.assertEqual(trace['completed_rounds'], 1)
            terminal = next(c for c in trace['candidates'] if c['move']=='pass')
            self.assertTrue(terminal['value']['exact'])
            self.assertEqual(len(kata.queries), 2)

    def test_policy_pass_without_preceding_pass_still_compares_continuations(self):
        for color in ('B', 'W'):
            (move, trace), _ = self.run_choice(color=color, root=policy(3, 'pass', 'A3'),
                values={'pass': .1 if color=='B' else .9, 'A3': .9 if color=='B' else .1})
            self.assertEqual(move, 'A3')
            self.assertFalse(trace['pass_agreement'])
            self.assertEqual(trace['completed_rounds'], 1)

    def test_pass_scoring_overrun_returns_measured_fallback_not_agreement(self):
        clock = Clock()
        kata = FakeKata(clock, root=policy(3, 'pass'))
        def slow_score(ref, color):
            clock.now += .2
            return {'exact': True, 'winrate': 0, 'score': -.5}
        with patch('neural_led._terminal', slow_score):
            move, trace = choose(kata, [['W','pass']], 'B', 3, .5, 100, clock=clock)
        self.assertEqual(move, 'pass')
        self.assertFalse(trace['pass_agreement'])
        self.assertTrue(trace['fallback'])
        self.assertGreater(trace['overshoot_ms'], 0)

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
