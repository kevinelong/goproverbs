import copy
import unittest
from lab import Referee
from safety import capture_proof, groups


class SafetyTests(unittest.TestCase):
    def test_immediate_capture_and_defender_escape_are_distinct(self):
        ref = Referee(5)
        ref.play('B','A1'); ref.play('W','B1')
        before = copy.deepcopy(ref.__dict__)
        self.assertEqual(capture_proof(ref,'A1','W','W',1)['status'],'capture-proven-within-horizon')
        self.assertEqual(capture_proof(ref,'A1','W','B',2)['status'],'unknown')
        self.assertEqual(ref.__dict__,before)

    def test_budget_exhaustion_is_unknown_not_life_or_death(self):
        ref=Referee(5); ref.play('B','C3')
        self.assertEqual(capture_proof(ref,'C3','W','W',8,1)['status'],'unknown')
        self.assertEqual(groups(ref)[0]['status'],'unknown')

    def test_two_eye_group_is_not_reported_captured(self):
        ref=Referee(5)
        for move in ['A2','B2','C2','D2','D1','B1']: ref.play('B',move)
        for move in ['A1','C1']:
            with self.assertRaises(AssertionError): copy.deepcopy(ref).play('W',move)
        result=capture_proof(ref,'B2','W','W',4,1000)
        self.assertEqual(result['status'],'unknown')


if __name__ == '__main__': unittest.main()
