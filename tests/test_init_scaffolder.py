import os
import sys
import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class TestInitScaffolder(unittest.TestCase):
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

    def test_init_json_creates_files(self):
        with TemporaryDirectory() as td:
            target = Path(td) / "proj"
            code, out, err = self.run_cli("init", str(target), "--format", "json")
            self.assertEqual(code, 0)
            obj = json.loads(out)
            self.assertTrue(obj["ok"])
            self.assertEqual(obj["command"], "init")
            self.assertEqual(Path(obj["path"]), target.resolve())
            # Key files exist
            self.assertTrue((target / "eidon.toml").exists())
            self.assertTrue((target / "README.md").exists())
            # Logs should be on stderr only (may be empty depending on log level)
            self.assertNotIn("Initialized", out)

    def test_init_refuses_overwrite_without_force(self):
        with TemporaryDirectory() as td:
            target = Path(td) / "proj"
            target.mkdir()
            (target / "some.txt").write_text("pre-existing", encoding="utf-8")
            code, out, err = self.run_cli("init", str(target))
            self.assertEqual(code, 4)
            self.assertIn("exists and is not empty", err)

    def test_init_force_overwrites(self):
        with TemporaryDirectory() as td:
            target = Path(td) / "proj"
            target.mkdir()
            # Pre-existing config that should be overwritten
            (target / "eidon.toml").write_text('default_name = "Old"\n', encoding="utf-8")
            code, out, err = self.run_cli("init", str(target), "--force")
            self.assertEqual(code, 0)
            content = (target / "eidon.toml").read_text(encoding="utf-8")
            self.assertIn('default_name = "World"', content)
