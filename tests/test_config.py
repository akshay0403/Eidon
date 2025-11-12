import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from eidon.__main__ import main


class TestConfig(unittest.TestCase):
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

    def test_default_name_from_defaults(self):
        # No user/project config, no env → built-in default
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_cli("hello", env={"HOME": tmp}, cwd=tmp)
            self.assertEqual(code, 0)
            self.assertEqual(out.strip(), "Hello, World!")

    def test_env_override_beats_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_cli("hello", env={"HOME": tmp, "EIDON_DEFAULT_NAME": "EnvName"}, cwd=tmp)
            self.assertEqual(code, 0)
            self.assertEqual(out.strip(), "Hello, EnvName!")

    def test_cli_beats_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_cli("hello", "--name", "CLI", env={"HOME": tmp, "EIDON_DEFAULT_NAME": "EnvName"}, cwd=tmp)
            self.assertEqual(code, 0)
            self.assertEqual(out.strip(), "Hello, CLI!")

    def test_project_config_beats_user(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as proj:
            user_cfg = Path(home) / ".config" / "eidon"
            user_cfg.mkdir(parents=True, exist_ok=True)
            (user_cfg / "config.toml").write_text("[eidon]\ndefault_name = 'UserName'\n", encoding="utf-8")

            (Path(proj) / "eidon.toml").write_text("[eidon]\ndefault_name = 'ProjectName'\n", encoding="utf-8")

            code, out = self.run_cli("hello", env={"HOME": home}, cwd=proj)
            self.assertEqual(code, 0)
            self.assertEqual(out.strip(), "Hello, ProjectName!")
