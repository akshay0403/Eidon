import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from eidon.__main__ import main


class TestConfigShow(unittest.TestCase):
    def run_cli(self, *argv, env=None, cwd=None):
        old_env = os.environ.copy()
        old_cwd = os.getcwd()
        try:
            if env:
                os.environ.update(env)
            if cwd:
                os.chdir(cwd)
            out = io.StringIO()
            # logs go to stderr; we only capture stdout here
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                code = main(list(argv))
            return code, out.getvalue()
        finally:
            os.chdir(old_cwd)
            os.environ.clear()
            os.environ.update(old_env)

    def test_show_with_sources_env(self):
        code, out = self.run_cli("config", "show", "--with-sources", env={"EIDON_DEFAULT_NAME": "EnvName"})
        self.assertEqual(code, 0)
        self.assertIn("default_name: EnvName", out)
        self.assertIn("env:EIDON_DEFAULT_NAME", out)

    def test_config_flag_overrides_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "custom.toml"
            cfg.write_text("[eidon]\ndefault_name = 'FromCustom'\n", encoding="utf-8")
            code, out = self.run_cli("--config", str(cfg), "hello")
            self.assertEqual(code, 0)
            # hello prints to stdout; confirm it used the custom file
            self.assertIn("Hello, FromCustom!", out)
