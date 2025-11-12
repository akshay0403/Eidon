import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from eidon.__main__ import main


class TestCLI(unittest.TestCase):
    def run_cli(self, *argv, env=None, cwd=None):
        old_env = os.environ.copy()
        old_cwd = os.getcwd()
        try:
            if env:
                os.environ.update(env)
            if cwd:
                os.chdir(cwd)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main(list(argv))
            return code, buf.getvalue()
        finally:
            os.chdir(old_cwd)
            os.environ.clear()
            os.environ.update(old_env)

    def test_hello_with_name(self):
        code, out = self.run_cli("hello", "--name", "Akshay")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "Hello, Akshay!")

    def test_hello_default(self):
        # Run in a clean temp dir with a clean HOME so no config is picked up
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_cli("hello", env={"HOME": tmp}, cwd=tmp)
            self.assertEqual(code, 0)
            self.assertEqual(out.strip(), "Hello, World!")
