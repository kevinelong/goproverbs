"""Independent referee checks and release-engine protocol integration tests."""
import copy
import tempfile
import unittest
from pathlib import Path

from lab import GTP, ROOT, Referee, load_cases, setup


class RefereeTests(unittest.TestCase):
    def test_area_neutral_and_enclosed_region(self):
        ref = Referee(3)
        self.assertEqual(ref.margin(), -0.5)
        for move in ["B1", "B2", "B3"]:
            ref.play("B", move)
        ref.play("W", "C2")
        self.assertEqual(ref.margin(), 4.5)

    def test_capture_before_suicide(self):
        ref = Referee(3)
        for move in ["A2", "C2", "B3"]:
            ref.play("B", move)
        for move in ["A1", "C1", "B2"]:
            ref.play("W", move)
        ref.play("B", "B1")
        self.assertEqual(ref.board.count("W"), 0)
        self.assertEqual(ref.board.count("B"), 4)

    def test_multi_stone_suicide_and_atomic_superko_rejection(self):
        ref = Referee(5)
        for move in ["A1", "B1"]:
            ref.play("B", move)
        for move in ["A2", "C1", "C2", "B3"]:
            ref.play("W", move)
        ref.play("B", "B2")
        self.assertEqual(ref.board.count("B"), 0)
        ref = Referee(3)
        ref.play("W", "A2")
        ref.play("W", "B1")
        before = copy.deepcopy(ref.__dict__)
        with self.assertRaisesRegex(AssertionError, "superko"):
            ref.play("B", "A1")
        self.assertEqual(ref.__dict__, before)


class ReleaseProtocolTests(unittest.TestCase):
    def engine(self, size=5):
        return GTP(ROOT / "target/release/goproverbs.exe", size=size)

    def test_scoring_finish_and_undo(self):
        with self.engine(3) as engine:
            engine.command("komi 0.5")
            engine.command("play B A1")
            engine.command("play W C3")
            with self.assertRaises(RuntimeError):
                engine.command("final_score")
            engine.command("play B pass")
            engine.command("play W pass")
            self.assertEqual(engine.command("final_score"), "W+0.5")
            self.assertIn("RE[W+0.5]", engine.command("gp-sgf"))
            with self.assertRaises(RuntimeError):
                engine.command("play B B2")
            engine.command("undo")
            engine.command("play W B2")

    def test_search_budget_nonmutation_and_last_trace(self):
        with self.engine() as engine:
            engine.command("gp-limits 1000 1 3 6")
            before = engine.command("showboard")
            report = engine.command("gp-search B")
            self.assertIn("depth=0", report)
            self.assertIn("limited=true", report)
            self.assertEqual(engine.command("showboard"), before)
            move = engine.command("genmove B")
            ref = Referee(5)
            ref.play("B", move)
            ref.compare(engine.command("showboard"))
            self.assertIn(f"move={move}", engine.command("gp-last-search"))
            engine.command("undo")
            self.assertEqual(engine.command("showboard"), before)
            with self.assertRaises(RuntimeError):
                engine.command("gp-last-search")

    def test_profiles_roundtrip_and_failed_load_is_atomic(self):
        # Relative paths avoid GTP's whitespace-delimited filename limitation.
        with tempfile.TemporaryDirectory(prefix="gp-profile-", dir=ROOT) as directory:
            saved = Path(directory) / "saved.weights"
            invalid = Path(directory) / "invalid.weights"
            invalid.write_text("capture=1\ntypo=2\n", encoding="ascii")
            with self.engine() as engine:
                engine.command("gp-weight capture 3.25")
                before = engine.command("gp-weights")
                engine.command(f"gp-save-weights {saved}")
                engine.command("gp-weight capture 8")
                engine.command(f"gp-load-weights {saved}")
                self.assertEqual(engine.command("gp-weights"), before)
                with self.assertRaises(RuntimeError):
                    engine.command(f"gp-load-weights {invalid}")
                self.assertEqual(engine.command("gp-weights"), before)

    def test_corrected_rescue_label_and_snapback(self):
        cases = {c["id"]: c for c in load_cases(ROOT / "benchmarks/fixtures.json")}
        with self.engine() as engine:
            ref = setup(engine, cases["rescue-edge-pair"])
            engine.command("play B B1")
            ref.play("B", "B1")
            ref.compare(engine.command("showboard"))
            _, liberties = ref.group(ref.board, 7 * 9)  # A2 on 9x9
            self.assertEqual(len(liberties), 2)
            setup(engine, cases["snapback-trap"])
            engine.command("gp-limits 1000 50000 2 12")
            greedy = engine.command("gp-candidates B").split()[0]
            self.assertEqual(greedy, "C1")
            search = engine.command("gp-search B").splitlines()[0]
            self.assertIn("depth=2", search)
            self.assertNotIn("move=C1 ", search)

    def test_leaf_explanation_accounts_for_search_score(self):
        with self.engine() as engine:
            engine.command("play B B2")
            engine.command("gp-limits 1000 5000 2 12")
            lines = engine.command("gp-search W").splitlines()
            fields = dict(field.split("=", 1) for field in lines[0].split())
            self.assertEqual(fields["depth"], "2")
            start = lines.index("Leaf evaluation from the root player's perspective:")
            total = 0.0
            for line in lines[start + 1:]:
                if line.startswith("Alternating move preferences"):
                    total += float(line.rsplit(":", 1)[1])
                    break
                total += float(line.rsplit("=", 1)[1])
            self.assertAlmostEqual(total, float(fields["score"]), delta=0.005)



class TacticalExtensionTests(unittest.TestCase):
    def test_extension_budget_pv_legality_and_nonmutation(self):
        case = next(c for c in load_cases(ROOT / 'benchmarks/fixtures.json') if c['id'] == 'rescue-single')
        case = dict(case, size=5)
        with GTP(ROOT / 'target/release/goproverbs.exe', size=5, nodes=5000, depth=1, beam=12, tactical=2) as engine:
            ref = setup(engine, case)
            before = engine.command('showboard')
            trace = engine.command('gp-search B').splitlines()
            fields = dict(part.split('=', 1) for part in trace[0].split())
            self.assertEqual(fields['depth'], '1')
            self.assertGreater(int(fields['tactical_nodes']), 0)
            self.assertLessEqual(int(fields['nodes']), 5000)
            line = trace[1].removeprefix('pv=').split()
            self.assertLessEqual(len(line), 3)
            for index, move in enumerate(line):
                ref.play('B' if index % 2 == 0 else 'W', move)
            self.assertEqual(engine.command('showboard'), before)
            with self.assertRaises(RuntimeError):
                engine.command('gp-tactical 5')
            again = engine.command('gp-search B').splitlines()[0]
            for key in ['move', 'score', 'depth', 'nodes', 'tactical_nodes']:
                self.assertEqual(dict(p.split('=', 1) for p in again.split())[key], fields[key])
            engine.command('gp-limits 1000 1 4 12')
            tiny = engine.command('gp-search B')
            self.assertIn('depth=0', tiny)
            self.assertIn('limited=true', tiny)

    def test_no_extensions_at_quiet_leaves(self):
        with GTP(ROOT / 'target/release/goproverbs.exe', size=9, nodes=5000, depth=1, beam=12, tactical=4) as engine:
            trace = engine.command('gp-search B')
            self.assertIn('depth=1', trace)
            self.assertIn('tactical_nodes=0', trace)


class SearchModeProtocolTests(unittest.TestCase):
    def test_hybrid_trace_and_failed_setting_are_atomic(self):
        case = next(c for c in load_cases(ROOT / 'benchmarks/fixtures.json') if c['id'] == 'snapback-trap')
        with GTP(ROOT / 'target/release/goproverbs.exe', size=5, nodes=50000, depth=3, beam=12, search_mode='hybrid') as engine:
            ref = setup(engine, case)
            before = engine.command('showboard')
            lines = engine.command('gp-search B').splitlines()
            fields = dict(p.split('=', 1) for p in lines[0].split())
            self.assertEqual(fields['mode'], 'hybrid')
            self.assertEqual(fields['depth'], '3')
            self.assertNotEqual(fields['move'], 'C1')
            self.assertTrue(any('C1 heuristic=' in line and 'verified=' in line for line in lines))
            for index, move in enumerate(lines[1].removeprefix('pv=').split()):
                ref.play('B' if index % 2 == 0 else 'W', move)
            self.assertEqual(engine.command('showboard'), before)
            for invalid in ['gp-mode nonsense', 'gp-shortlist 0']:
                with self.assertRaises(RuntimeError):
                    engine.command(invalid)
            again = dict(p.split('=', 1) for p in engine.command('gp-search B').splitlines()[0].split())
            for key in ['move', 'score', 'depth', 'mode', 'nodes']:
                self.assertEqual(fields[key], again[key])

    def test_full_and_minimax_agree_through_gtp(self):
        with GTP(ROOT / 'target/release/goproverbs.exe', size=3, nodes=50000, depth=3, beam=1) as engine:
            engine.command('play B B2')
            results = []
            for mode in ['full', 'minimax']:
                engine.command(f'gp-mode {mode}')
                fields = dict(p.split('=', 1) for p in engine.command('gp-search W').splitlines()[0].split())
                self.assertEqual(fields['depth'], '3')
                results.append(fields)
            self.assertEqual(results[0]['move'], results[1]['move'])
            self.assertEqual(results[0]['score'], results[1]['score'])
            self.assertLessEqual(int(results[0]['nodes']), int(results[1]['nodes']))

    def test_opening_scope_in_protocol(self):
        with GTP(ROOT / 'target/release/goproverbs.exe') as engine:
            for size in [9, 13, 19, 25]:
                engine.command(f'boardsize {size}')
                report = engine.command('gp-explain B C3')
                self.assertEqual('empty_corner' in report, size == 19)
                engine.command('play B D4')
                report = engine.command('gp-explain W C3')
                self.assertEqual('early_33' in report, size == 19)


if __name__ == '__main__':
    unittest.main()
