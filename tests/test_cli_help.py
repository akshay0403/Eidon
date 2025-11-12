import io
import unittest
from contextlib import redirect_stdout, redirect_stderr
from eidon.__main__ import main


class TestCLIHelp(unittest.TestCase):
    def test_root_help(self):
        # argparse prints help and exits 0
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                main(["--help"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("Eidon command-line interface.", out.getvalue())

    def test_hello_help(self):
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                main(["hello", "--help"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("Name to greet", out.getvalue())
