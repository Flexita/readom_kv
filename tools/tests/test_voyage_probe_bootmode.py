# SPDX-License-Identifier: Apache-2.0
"""The bootmode-only Voyage probe never invents main."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'tools/voyage-probe-bootmode.sh'


class VoyageProbeBootmode(unittest.TestCase):
    def _run(self, mode_text):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'root'
            (root / 'proc').mkdir(parents=True)
            (root / 'proc' / 'bootmode').write_text(mode_text)
            out = Path(tmp) / 'out.txt'
            env = os.environ.copy()
            env['VOYAGE_PROBE_ROOT'] = str(root)
            env['VOYAGE_PROBE_OUT'] = str(out)
            done = subprocess.run(['sh', str(SCRIPT)], env=env,
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            return out.read_text()

    def test_main_is_reported(self):
        text = self._run('main\n')
        self.assertIn('bootmode: main', text)
        self.assertIn('result: ok', text)

    def test_empty_is_not_main(self):
        text = self._run('')
        self.assertIn('bootmode: withheld (empty)', text)
        self.assertIn('result: partial', text)
        self.assertNotRegex(text, r'(?m)^bootmode: main$')

    def test_script_stays_narrow(self):
        # Strip comments; only the executable body must stay narrow.
        body = '\n'.join(
            line for line in SCRIPT.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith('#'))
        for banned in ('kcore', '/dev/mem', 'atags', 'board_id', 'mac_addr',
                       'Readom', 'insmod', 'modprobe'):
            self.assertNotIn(banned, body)
        self.assertIn('/proc/bootmode', body)


if __name__ == '__main__':
    unittest.main()
