import subprocess
import sys
import unittest


class TestVersionFlag(unittest.TestCase):
    def test_version_flag_exits_zero_and_prints_version(self):
        proc = subprocess.run(
            [sys.executable, "-m", "eidon", "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("eidon ", proc.stdout)
        self.assertEqual(proc.stderr, "")


if __name__ == "__main__":
    unittest.main()
