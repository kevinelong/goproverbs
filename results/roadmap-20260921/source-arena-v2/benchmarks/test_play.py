import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from lab import ROOT


class PlayTests(unittest.TestCase):
    def test_scripted_play_save_load_undo_and_explain(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'session.sgf'
            commands=f'A1\nrank\nexplain\nsave "{path}"\nundo\nload "{path}"\nquit\n'
            result=subprocess.run([sys.executable,str(ROOT/'benchmarks/play.py'),'--size','5','--time-ms','10'],input=commands,text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue(path.exists())
            self.assertNotIn('Error:',result.stdout)
            self.assertIn('Engine:',result.stdout)

    def test_white_gets_an_engine_opening(self):
        result=subprocess.run([sys.executable,str(ROOT/'benchmarks/play.py'),'--size','5','--time-ms','10','--color','W'],input='quit\n',text=True,capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Engine:',result.stdout)
        self.assertIn('W>',result.stdout)


if __name__=='__main__': unittest.main()
