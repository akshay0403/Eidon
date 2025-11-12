import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout

from eidon.__main__ import main


class TestLogging(unittest.TestCase):
    def run_cli(self, *argv, env=None):
        old_env = os.environ.copy()
        try:
            if env:
                os.environ.update(env)
            err = io.StringIO()
            # Silence stdout (prints) and capture stderr (logs)
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                code = main(list(argv))
            return code, err.getvalue()
        finally:
            os.environ.clear()
            os.environ.update(old_env)

    def test_default_is_quiet_warning(self):
        code, err = self.run_cli("hello", "--name", "X")
        self.assertEqual(code, 0)
        self.assertNotIn("Greeting sent", err)          # INFO hidden
        self.assertNotIn("Preparing greeting", err)     # DEBUG hidden

    def test_cli_overrides_to_info(self):
        code, err = self.run_cli("--log-level", "INFO", "hello", "--name", "Y")
        self.assertEqual(code, 0)
        self.assertIn("Greeting sent", err)             # INFO visible
        self.assertNotIn("Preparing greeting", err)     # DEBUG hidden

    def test_env_overrides_to_debug(self):
        code, err = self.run_cli("hello", "--name", "Z", env={"EIDON_LOG_LEVEL": "DEBUG"})
        self.assertEqual(code, 0)
        self.assertIn("Greeting sent", err)             # INFO visible
        self.assertIn("Preparing greeting", err)        # DEBUG visible

    def test_cli_beats_env(self):
        code, err = self.run_cli("--log-level", "WARNING", "hello", env={"EIDON_LOG_LEVEL": "DEBUG"})
        self.assertEqual(code, 0)
        self.assertNotIn("Greeting sent", err)          # INFO hidden
        self.assertNotIn("Preparing greeting", err)     # DEBUG hidden
