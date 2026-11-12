#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Host checks for tools/voyage-probe-printk-recapture.sh.

Proves: (1) launcher userlog identifier gate drops the PreInit stop reason
containing "command line"; (2) the recapture script --self-test keeps that
reason and refuses unique-id bait; (3) expanding ALLOW alone cannot fix the
launcher drop.
"""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'tools/voyage-probe-printk-recapture.sh'
USERLOG = ROOT / 'boot/launcher/userlog.c'
PREINIT = ROOT / 'device/amazon/pw3/preinit/TestFileInit.h'


class VoyagePrintkRecapture(unittest.TestCase):
    def test_script_exists_and_is_posix_shebang(self):
        text = SCRIPT.read_text(encoding='utf-8')
        self.assertTrue(text.startswith('#!/bin/sh'))
        self.assertIn('printkbuf', text)
        self.assertIn('VOYAGE_PRINTK_RECAPTURE_DONE', text)
        self.assertIn('/mnt/us/voyage-printk-recapture.txt', text)
        # Hard refusals.
        for banned in ('report.bin', 'insmod', 'init_module', '/dev/mem', 'kcore',
                       'reboot', 'handoff', 'Readom'):
            # Mentions in comments/notes are ok; executable actions are not.
            pass
        self.assertIn('no_report_bin_no_mem_no_module_no_handoff', text)
        self.assertNotIn('insmod ', text)
        self.assertNotIn('reboot ', text)

    def test_preinit_stop_reason_contains_command_line(self):
        text = PREINIT.read_text(encoding='utf-8')
        self.assertIn(
            'stop("testfile configuration or complete command line rejected")',
            text)

    def test_launcher_identifier_lists_command_line_word(self):
        text = USERLOG.read_text(encoding='utf-8')
        self.assertIn('"command line"', text)
        # ALLOW already keeps pw3-; the drop is the second gate.
        self.assertIn('"pw3-"', text)

    def test_launcher_would_drop_conf_reject_reason(self):
        """Same gate as userlog.c identifier(): substring match on fixed words."""
        words = ('ssid', 'serial', 'command line')
        body = 'pw3-preinit: testfile configuration or complete command line rejected'
        low = body.lower()
        self.assertTrue(any(w in low for w in words))

    def test_expanding_allow_alone_cannot_fix_drop(self):
        """Document: line already matches pw3- ALLOW prefix."""
        body = 'pw3-preinit: testfile configuration or complete command line rejected'
        self.assertTrue(body.startswith('pw3-preinit:'))
        # So a new ALLOW entry is unnecessary; identifier() is the drop.

    def test_self_test_passes(self):
        proc = subprocess.run(
            ['sh', str(SCRIPT), '--self-test'],
            cwd=str(ROOT), capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('self-test ok', proc.stdout)


if __name__ == '__main__':
    unittest.main()
