import unittest
from sgf_io import read_game, replay, parse


class SgfTests(unittest.TestCase):
    def test_escape_variation_and_collection(self):
        text = r'(;FF[4]GM[1]SZ[19]RU[Tromp-Taylor]C[a\]b\\c];B[dd](;W[pp])(;W[dp]))(;SZ[9];B[])'
        g = read_game(text)
        self.assertEqual(g['nodes'][0]['C'], ['a]b\\c'])
        self.assertEqual(g['moves'], [['B','D16'], ['W','Q4']])
        self.assertEqual(g['ignored_variations'], 1)
        self.assertEqual(g['collection_games'], 2)
        self.assertEqual(read_game(text, 1)['moves'], [['B','pass']])
        replay(g)

    def test_pass_coordinates_and_rule_conversion(self):
        g = read_game('(;SZ[19]KM[7.5];B[ia];W[tt];B[])')
        self.assertEqual(g['moves'][0], ['B', 'J19'])
        with self.assertRaises(ValueError): replay(g)
        self.assertEqual(replay(g, True).passes, 2)

    def test_reject_malformed_and_unsupported(self):
        for text in ['', '(;C[x)', '(;SZ[19]SZ[9])', '(;AB[aa])', '(;SZ[19:13])',
                     '(;GM[2])', '(;B[aa]W[bb])', '(;SZ[9];B[zz])', '(;KM[NaN])']:
            with self.assertRaises(ValueError, msg=text): read_game(text)
        with self.assertRaises(ValueError): parse('(;C[unfinished\\')

    def test_replay_occupied_and_post_terminal(self):
        with self.assertRaises(AssertionError):
            replay(read_game('(;RU[Tromp-Taylor];B[aa];W[aa])'))
        with self.assertRaises(ValueError):
            replay(read_game('(;RU[Tromp-Taylor];B[];W[];B[aa])'))


if __name__ == '__main__': unittest.main()
