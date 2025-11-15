import os
import subprocess
import sys
import unittest


class TestErrorMapping(unittest.TestCase):
    def test_eidonerror_is_mapped_to_exit_code_and_message(self):
        env = os.environ.copy()
        env["EIDON_TEST_RAISE"] = "EidonError"

        proc = subprocess.run(
            [sys.executable, "-m", "eidon", "hello"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

        self.assertEqual(proc.returncode, 7)     # from hello command injection
        self.assertIn("boom", proc.stderr)       # friendly message on stderr


if __name__ == "__main__":
    unittest.main()
