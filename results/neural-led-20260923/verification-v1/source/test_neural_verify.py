import copy
import unittest

from neural_led import DecisionError
from neural_verify import checked_value, choose_verified, select_move
from neural_verify_experiment import depth_gate, quality_gate
from test_neural_led import Clock, FakeKata, policy


class VerifyTests(unittest.TestCase):
    def run_case(self, color='B', costs=None, change=None, **kwargs):
        clock=Clock()
        def mutate(index,result):
            result['rootInfo']['visits']=16
            if index>=4:
                result['rootInfo']['winrate']=(.5 if index==4 else (.51 if color=='B' else .49))
            if change: change(index,result)
        values={'A3':.5,'B3':.7 if color=='B' else .3,'C3':.5}
        kata=FakeKata(clock,values=values,costs=costs,change=mutate,**kwargs)
        result=choose_verified(kata,[],color,3,.5,200,16,clock=clock)
        return result,kata

    def test_both_colors_and_single_shared_deadline(self):
        for color in ('B','W'):
            (move,trace),kata=self.run_case(color)
            self.assertEqual(move,'B3')
            self.assertTrue(trace['verification_complete'])
            self.assertEqual([q['maxVisits'] for q,d in kata.queries],[1,1,1,1,16,16])
            self.assertEqual(len({d for q,d in kata.queries}),1)
            self.assertEqual(kata.queries[-1][0]['moves'],[[color,'B3']])

    def test_threshold_rejects_small_or_negative_gain(self):
        for gain in (-.1,0,.004999):
            self.assertEqual(select_move('a','b',{'a':{'winrate':0},'b':{'winrate':gain}}),'a')
        self.assertEqual(select_move('a','b',{'a':{'winrate':0},'b':{'winrate':.005}}),'b')
        (move,trace),_=self.run_case(change=lambda i,r:r['rootInfo'].update(winrate=.503) if i==5 else None)
        self.assertEqual(move,'A3')
        self.assertTrue(trace['verification_complete'])

    def test_late_and_partial_verification_fall_back_without_using_values(self):
        (move,trace),_=self.run_case(costs=[.001]*5+[.3])
        self.assertEqual(move,'A3')
        self.assertTrue(trace['verification_fallback'])
        self.assertFalse(trace['verification_complete'])
        self.assertNotIn('B3',trace['values'])
        (move,trace),_=self.run_case(fail_at=(5,TimeoutError('budget')))
        self.assertEqual(move,'A3')
        self.assertTrue(trace['verification_fallback'])

    def test_invalid_reference_is_error_not_fallback(self):
        for mutation in (lambda r:r.update(id='wrong'),lambda r:r.update(warning='altered'),
                         lambda r:r.update(isDuringSearch=True),
                         lambda r:r['rootInfo'].update(visits=15),
                         lambda r:r['rootInfo'].update(visits=float('inf')),
                         lambda r:r['rootInfo'].update(currentPlayer='B'),
                         lambda r:r['rootInfo'].update(winrate=float('nan'))):
            with self.assertRaises(DecisionError):
                self.run_case(change=lambda i,r:mutation(r) if i==4 else None)

    def test_policy_agreement_pass_and_terminal_skip_verification(self):
        clock=Clock(); kata=FakeKata(clock,root=policy(3,'pass','A3','B3'))
        moves=[['W','pass']]; before=copy.deepcopy(moves)
        move,trace=choose_verified(kata,moves,'B',3,.5,200,8,clock=clock)
        self.assertEqual(move,'pass'); self.assertTrue(trace['pass_agreement'])
        self.assertFalse(trace['verification_attempted']); self.assertEqual(len(kata.queries),1)
        self.assertEqual(moves,before)
        clock=Clock(); kata=FakeKata(clock)
        move,trace=choose_verified(kata,[['B','pass'],['W','pass']],'B',3,.5,200,8,clock=clock)
        self.assertIsNone(move); self.assertEqual(len(kata.queries),0)
        clock=Clock(); kata=FakeKata(clock,values={'A3':.9})
        move,trace=choose_verified(kata,[],'B',3,.5,200,8,clock=clock)
        self.assertEqual(move,'A3'); self.assertFalse(trace['verification_attempted'])

    def test_cancellation_after_baseline_never_starts_verification(self):
        clock=Clock(); kata=FakeKata(clock,values={'B3':.9})
        checks=[0]
        def cancel():
            # Baseline has finished when the fourth result has arrived; its
            # cancellation check itself returns policy and skips verification.
            checks[0]+=1
            return len(kata.queries)>=4
        move,trace=choose_verified(kata,[],'B',3,.5,200,8,clock=clock,cancelled=cancel)
        self.assertEqual(move,'A3'); self.assertFalse(trace['verification_complete'])
        self.assertEqual(len(kata.queries),4)

    def test_reference_normalizes_white_score_and_winrate(self):
        r=dict(id='x',rootInfo=dict(currentPlayer='B',visits=128,winrate=.8,scoreLead=12))
        value=checked_value(r,'x','B','W',128)
        self.assertAlmostEqual(value['winrate'],.2); self.assertEqual(value['score'],-12)


def timing_row(role='neural',visits=16):
    return dict(role=role,visits=visits,ms=100,legal=True,
        trace=dict(verification_complete=True,verification_fallback=False,baseline=dict(fallback=False)))


class GateTests(unittest.TestCase):
    def test_depth_selection_uses_timing_and_requires_each_role(self):
        rows=[timing_row('neural' if i<10 else 'combined',v) for v in (4,8,16) for i in range(20)]
        self.assertEqual(depth_gate(rows)['selected_visits'],16)
        rows[-1]['ms']=181
        self.assertEqual(depth_gate(rows)['selected_visits'],8)
        for row in rows:
            if row['role']=='combined': row['trace']['verification_complete']=False
        self.assertIsNone(depth_gate(rows)['selected_visits'])

    def test_quality_gate_both_depths_roles_and_severe_harm(self):
        rows=[dict(opening=str(i//2),role='neural' if i<20 else 'combined',decision=timing_row(),
              deltas={str(v):dict(versus_current=.02,versus_policy=.01) for v in (128,512)}) for i in range(40)]
        self.assertTrue(quality_gate(rows)['passed'])
        changed=copy.deepcopy(rows)
        for r in changed: r['deltas']['128']['versus_current']=0
        self.assertFalse(quality_gate(changed)['passed'])
        changed=copy.deepcopy(rows)
        for v in ('128','512'): changed[0]['deltas'][v]['versus_current']=-.06
        self.assertEqual(quality_gate(changed)['severe_harm'],1)
        self.assertFalse(quality_gate(changed)['passed'])
        changed=copy.deepcopy(rows); changed[0]['decision']['trace']['verification_fallback']=True
        self.assertFalse(quality_gate(changed)['passed'])
        changed=copy.deepcopy(rows)
        for r in changed:
            if r['role']=='combined':
                for v in ('128','512'): r['deltas'][v]['versus_current']=-.001
        self.assertFalse(quality_gate(changed)['passed'])
        self.assertFalse(quality_gate([])['passed'])


if __name__=='__main__': unittest.main()
