# SPDX-License-Identifier: Apache-2.0
"""Regression: Voyage profile-3 must not hard-E105 before install_prepare.

The tip-5eeb9b5 USB offline kit failed on-device with helper_exit=3 and
  VOYAGE_INSTALL_BLOCKED identity has not been measured; no system image was written
even though dd_voyage_5_13_6.identity_ready==1 in the same ELF. That exact log
line (with the "; no system image was written" suffix) came only from a
compile-time `#if CHECK_PROFILE == 3` early exit in helper.c main(), not from
install_prepare()'s identity_ready check (which prints the shorter line).
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / 'boot/launcher/helper.c'
TEMPLATE = ROOT / 'boot/launcher/launcher-template.sh'
PACK = ROOT / 'tools/voyage-pack-usb-offline-experimental.py'
SPLIT = ROOT / 'tools/voyage-split-usb-kit-agent-store.py'
PROBE = ROOT / 'tools/voyage-probe-original-boot.sh'


class VoyageProfile3PrewriteGate(unittest.TestCase):
    def test_helper_has_no_hard_early_e105_block(self):
        text = HELPER.read_text()
        # The exact device-log string must not appear as a puts/printf target.
        self.assertNotIn(
            'identity has not been measured; no system image was written',
            text,
            'hard-block log string must be gone from helper.c',
        )
        # install_prepare still fail-closes when identity_ready is 0.
        self.assertIn('VOYAGE_INSTALL_BLOCKED identity has not been measured', text)
        self.assertIn('ENTRY_PROFILE.identity_ready', text)
        self.assertIn('dd_device_matches', text)
        self.assertIn('#define ENTRY_PROFILE dd_voyage_5_13_6', text)

    def test_profile3_uses_voyage_uname_not_qemu_smoke(self):
        text = HELPER.read_text()
        self.assertIn('#2 PREEMPT Thu Apr 8 09:39:57 UTC 2021', text)
        # Profile-3 branch must exist before the qemu #else.
        voyage_uname = text.find('CHECK_PROFILE == 3')
        smoke = text.find('-pw3-core-smoke')
        self.assertGreater(voyage_uname, 0)
        # The stock_profile voyage branch mentions the measured version string.
        stock = text.find('check=stock_profile')
        self.assertGreater(stock, 0)
        # Ensure voyage version appears near a CHECK_PROFILE == 3 uname gate.
        self.assertIsNotNone(re.search(
            r'#elif CHECK_PROFILE == 3\s*/\*.*?\*/\s*if \(strcmp\(u\.release.*#2 PREEMPT Thu Apr 8',
            text,
            flags=re.S,
        ))
        # QEMU smoke require must remain only in the final #else (profile 2).
        else_smoke = re.search(
            r'#else\s*\n\s*\(void\)exact_file; require\(strstr\(u\.release, "-pw3-core-smoke"\)',
            text,
        )
        self.assertIsNotNone(else_smoke)

    def test_profile3_pins_voyage_eips(self):
        text = HELPER.read_text()
        self.assertIn('7916bee55c7ec9ab4d2da5859d5b27e3caee77dd971aa93d01fccc8b2fdd6259', text)
        self.assertIn('61104', text)
        tmpl = TEMPLATE.read_text()
        self.assertIn('7916bee55c7ec9ab4d2da5859d5b27e3caee77dd971aa93d01fccc8b2fdd6259', tmpl)
        self.assertNotIn('VOYAGE BUILD CANNOT INSTALL', tmpl)

    def test_host_preflight_supports_split_volumes(self):
        pack = PACK.read_text()
        self.assertIn('LAYOUT=split', pack)
        self.assertIn('VOLUMES', pack)
        self.assertIn('missing payload', pack)
        self.assertTrue(SPLIT.is_file())
        split = SPLIT.read_text()
        self.assertIn('LAYOUT=split', split)
        self.assertIn('128', split)

    def test_original_boot_probe_is_privacy_safe(self):
        self.assertTrue(PROBE.is_file())
        text = PROBE.read_text()
        self.assertIn('hashes_and_sizes_only', text)
        self.assertIn('no_board_id_mac_serial', text)
        self.assertIn('/sbin/init', text)
        # Must refuse if unique tokens appear.
        self.assertIn('board_id|serial|mac', text)


if __name__ == '__main__':
    unittest.main()
