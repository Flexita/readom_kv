#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Host lock for t167u init_i2c_fault 1/2/3 FORCE_RST path diagnostics."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRV = Path('/home/builder/pw3-build/linux-android-core/drivers/input/touchscreen/zforce2.c')
BOOT = ROOT / 'device/amazon/pw3/initcheck/BootReport.cpp'
PATCH = ROOT / 'patches/android-core/1059-zforce2-init-i2c-fault.patch'


class VoyageZforceI2cFault(unittest.TestCase):
    def test_three_force_rst_sites_note_distinct_codes(self):
        if not DRV.is_file():
            self.skipTest('zforce2.c not on host')
        text = DRV.read_text(encoding='utf-8', errors='replace')
        self.assertIn('zforce_note_i2c_fault(1,', text)
        self.assertIn('zforce_note_i2c_fault(2,', text)
        self.assertIn('zforce_note_i2c_fault(3,', text)
        self.assertEqual(text.count('*result = ZF_ERR_FORCE_RST;'), 3)
        # No protocol/retry/power changes in this probe.
        self.assertIn('ZF_RESET_THRSHLD', text)
        self.assertNotIn('ZF_RESET_THRSHLD +', text)

    def test_fault_accumulates_across_retries_not_cleared_each_bslreset(self):
        if not DRV.is_file():
            self.skipTest('zforce2.c not on host')
        text = DRV.read_text(encoding='utf-8', errors='replace')
        # first sticky; count increments; bslReset path must not zero counters.
        self.assertIn('if (!zforce_i2c_fault_first)', text)
        self.assertIn('zforce_i2c_fault_count++;', text)
        # Session reset only at initialize() entry / init_data — not in bslReset.
        bsl = text[text.index('void bslReset'):text.index('void bslReset') + 800]
        self.assertNotIn('zforce_i2c_fault_count', bsl)
        self.assertIn('zforce_i2c_fault_cleared = 1;', text)
        self.assertIn('zforce_i2c_fault_last = 0;', text)

    def test_sysfs_attrs_cover_semantics_bootreport_withdrawn(self):
        """t167u sysfs stays on the kernel; t172u withdrew BootReport zforce probes."""
        if not DRV.is_file():
            self.skipTest('zforce2.c not on host')
        drv = DRV.read_text(encoding='utf-8', errors='replace')
        for attr in (
            'init_i2c_fault', 'init_i2c_fault_first', 'init_i2c_fault_count',
            'init_i2c_fault_counts', 'init_i2c_fault_cleared', 'init_i2c_xfer',
        ):
            self.assertIn(f'DEVICE_ATTR({attr}, 0444', drv)
        boot = BOOT.read_text(encoding='utf-8')
        # Cypress default path: no zforce FORCE_RST / i2c_fault report tags.
        for tag in (
            'zforce_i2c_fault', 'zforce_i2c_fault_first', 'zforce_i2c_fault_count',
            'zforce_i2c_fault_counts', 'zforce_i2c_fault_cleared', 'zforce_i2c_xfer',
        ):
            self.assertNotIn(tag, boot)
        self.assertIn('cyttsp4_mt', boot)
        # Privacy: no FRAME_START byte dump into report.
        self.assertNotIn('0xEE', boot)
        self.assertNotIn('frameHeader', boot)

    def test_patch_file_exists(self):
        self.assertTrue(PATCH.is_file())
        text = PATCH.read_text(encoding='utf-8', errors='replace')
        self.assertIn('zforce_note_i2c_fault(1,', text)
        self.assertIn('zforce_note_i2c_fault(2,', text)
        self.assertIn('zforce_note_i2c_fault(3,', text)


if __name__ == '__main__':
    unittest.main()
