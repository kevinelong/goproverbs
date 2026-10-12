import unittest
from corpus import openings
from paired_summary import summarize


class CorpusTests(unittest.TestCase):
    def test_openings_repeatable_distinct_and_even_length(self):
        first=openings(42,50)
        self.assertEqual(first,openings(42,50))
        self.assertEqual(len({str(x['moves']) for x in first}),50)
        self.assertTrue(all(len(x['moves'])%2==0 for x in first))

    def test_pair_scores_include_draws_and_exclude_incomplete_pairs(self):
        rows=[{'mode':'NH','opening':'a','variant_color':c,'finished':True,'result':'0','variant_won':False} for c in ['B','W']]
        rows += [{'mode':'NH','opening':'b','variant_color':'B','finished':False,'result':'unfinished','variant_won':False}]
        result=summarize(rows)['variants']['NH']
        self.assertEqual(result['mean_pair_score'],0.5)
        self.assertEqual(result['complete_pairs'],1)
        self.assertEqual(result['unfinished'],1)
        self.assertEqual(result['conservative_95_interval'],[0,1])


if __name__=='__main__': unittest.main()
