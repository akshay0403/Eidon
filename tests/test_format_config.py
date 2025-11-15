import os
import sys
import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class TestFormatConfig(unittest.TestCase):
    def run_cli(self, *args, env=None, cwd=None):
        proc = subprocess.run(
            [sys.executable, "-m", "eidon", *args],
            check=False,
            capture_output=True,
            text=True,
            env=env or os.environ.copy(),
            cwd=cwd,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def test_config_show_json_defaults(self):
        code, out, err = self.run_cli("config", "show", "--format", "json")
        self.assertEqual(code, 0)
        obj = json.loads(out)
        self.assertTrue(obj["ok"])
        self.assertEqual(obj["command"], "config.show")
        self.assertIn("default_name", obj)
        self.assertIn("log_level", obj)

    def test_config_show_json_with_sources_env(self):
        env = os.environ.copy()
        env["EIDON_DEFAULT_NAME"] = "EnvName"
        code, out, err = self.run_cli("config", "show", "--with-sources", "--format", "json", env=env)
        self.assertEqual(code, 0)
        obj = json.loads(out)
        self.assertEqual(obj["default_name"], "EnvName")
        self.assertIn("sources", obj)
        self.assertEqual(obj["sources"]["default_name"], "env:EIDON_DEFAULT_NAME")

    def test_config_show_json_with_override_file(self):
        with TemporaryDirectory() as td:
            cfg = Path(td) / "custom.toml"
            cfg.write_text('default_name = "FromCustom"\n', encoding="utf-8")
            code, out, err = self.run_cli("--config", str(cfg), "config", "show", "--format", "json")
            self.assertEqual(code, 0)
            obj = json.loads(out)
            self.assertEqual(obj["default_name"], "FromCustom")
