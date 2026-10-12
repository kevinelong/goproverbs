import copy
import unittest

from neural_disagreement import candidate_gate, guard_applies, key, reference_value


class DisagreementTests(unittest.TestCase):
    def test_guard_boundary_and_small_gain(self):
        choices={'root':{'policy_probability':.5,'value':{'winrate':0.0}},
                 'chosen':{'value':{'winrate':.019}}}
        self.assertTrue(guard_applies(choices))
        choices['chosen']['value']['winrate']=.02
        self.assertFalse(guard_applies(choices))
        choices['chosen']['value']['winrate']=.001
        choices['root']['policy_probability']=.499
        self.assertFalse(guard_applies(choices))

    def test_reference_perspective_and_incomplete_visit_rejection(self):
        r={'rootInfo':{'currentPlayer':'B','visits':512,'winrate':.8,'scoreLead':12.0}}
        value=reference_value(r,'B','W',512)
        self.assertAlmostEqual(value['winrate'],.2)
        self.assertEqual(value['score'],-12)
        for bad in ({'isDuringSearch':True}, {'_used_intermediate':True}):
            with self.assertRaises(ValueError): reference_value(dict(r,**bad),'B','W',512)
        for change in ({'visits':511},{'currentPlayer':'W'},{'winrate':float('nan')}):
            invalid=copy.deepcopy(r); invalid['rootInfo'].update(change)
            with self.assertRaises(ValueError): reference_value(invalid,'B','W',512)

    def test_gate_requires_both_depths_and_independent_opening_coverage(self):
        rows=[dict(stratum='confidence',split='development',opening=str(i//2),
                   deltas={str(v):{'root_minus_chosen':.02} for v in (128,512)}) for i in range(10)]
        self.assertTrue(candidate_gate(rows,'development')['passed'])
        self.assertFalse(candidate_gate(rows,'validation')['passed'])
        changed=copy.deepcopy(rows)
        for row in changed: row['deltas']['128']['root_minus_chosen']=-.01
        self.assertFalse(candidate_gate(changed,'development')['passed'])
        changed=copy.deepcopy(rows)
        for row in changed: row['opening']='one-opening'
        self.assertFalse(candidate_gate(changed,'development')['passed'])
        changed=copy.deepcopy(rows)
        for v in ('128','512'): changed[0]['deltas'][v]['root_minus_chosen']=-.06
        self.assertEqual(candidate_gate(changed,'development')['severe_harm'],1)
        self.assertFalse(candidate_gate(changed,'development')['passed'])

    def test_opening_split_hash_is_stable_and_color_independent(self):
        ids=[f'opening-{i}' for i in range(20)]
        dev=set(sorted(ids,key=lambda x:key(230925,x))[:10])
        self.assertEqual(dev,set(sorted(reversed(ids),key=lambda x:key(230925,x))[:10]))
        self.assertEqual(len(dev),10)


if __name__=='__main__': unittest.main()
