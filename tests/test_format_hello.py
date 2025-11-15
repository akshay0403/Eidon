import os
import sys
import json
import subprocess
import unittest
from tempfile import TemporaryDirectory


class TestFormatHello(unittest.TestCase):
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

    def test_hello_json_default(self):
    # Ensure pure defaults: no env override, no user config, no project config
        env = os.environ.copy()
        env.pop("EIDON_DEFAULT_NAME", None)
        with TemporaryDirectory() as td:
            env["XDG_CONFIG_HOME"] = td  # <-- prevent reading ~/.config/eidon/config.toml
            code, out, err = self.run_cli("hello", "--format", "json", env=env, cwd=td)
        self.assertEqual(code, 0)
        obj = json.loads(out)
        self.assertTrue(obj["ok"])
        self.assertEqual(obj["command"], "hello")
        self.assertEqual(obj["name"], "World")
        self.assertEqual(obj["greeting"], "Hello, World!")
        self.assertNotIn("Greeting sent", out)  # logs must be on stderr

    def test_hello_json_with_cli_name(self):
        code, out, err = self.run_cli("hello", "--name", "Akshay", "--format", "json")
        self.assertEqual(code, 0)
        obj = json.loads(out)
        self.assertEqual(obj["name"], "Akshay")
        self.assertEqual(obj["greeting"], "Hello, Akshay!")

    def test_hello_json_stdout_vs_stderr(self):
        env = os.environ.copy()
        env["EIDON_LOG_LEVEL"] = "INFO"
        code, out, err = self.run_cli("hello", "--name", "LogCheck", "--format", "json", env=env)
        self.assertEqual(code, 0)
        _ = json.loads(out)  # stdout must be valid JSON
        self.assertIn("Greeting sent", err)  # logs go to stderr
