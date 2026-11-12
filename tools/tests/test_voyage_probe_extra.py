# SPDX-License-Identifier: Apache-2.0
"""The extra Voyage probe keeps secrets out of a synthetic report."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'tools/voyage-probe-extra.sh'


class VoyageProbeExtra(unittest.TestCase):
    def test_self_test(self):
        done = subprocess.run(['sh', str(SCRIPT), '--self-test'],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn('self-test ok', done.stdout)


if __name__ == '__main__':
    unittest.main()
