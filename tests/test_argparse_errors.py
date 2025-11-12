import io
import unittest
from contextlib import redirect_stdout, redirect_stderr
from eidon.__main__ import main


class TestArgparseErrors(unittest.TestCase):
    def test_invalid_log_level(self):
        # invalid choice should print error to stderr and exit 2
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                main(["--log-level", "VERBOSE", "hello"])
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("invalid choice", err.getvalue())
