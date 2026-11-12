# SPDX-License-Identifier: Apache-2.0
"""The extra Voyage probe keeps secrets out of a synthetic report."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'tools/voyage-probe-extra.sh'
DOCS = (
    ROOT / 'docs/design/voyage-port.md',
    ROOT / 'docs/design/voyage-port.en.md',
)
EXTRA_REPORT_SHA256 = '47a04517af9e353643eaa98aba484ab4ea34adb899f3b49b6be79b4604e5a4ed'


class VoyageProbeExtra(unittest.TestCase):
    def test_self_test(self):
        done = subprocess.run(['sh', str(SCRIPT), '--self-test'],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn('self-test ok', done.stdout)

    def test_docs_record_the_ingested_extra_report(self):
        for path in DOCS:
            text = path.read_text()
            self.assertIn('47a04517', text, path.name)
            self.assertIn('bootmode', text.lower())
            self.assertIn('not collected', text.lower())
            self.assertNotRegex(text, r'bootmode:\s*main')


if __name__ == '__main__':
    unittest.main()
