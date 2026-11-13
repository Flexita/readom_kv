#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Voyage initcheck touch name — Cypress cyttsp4_mt (t172u).

Wrong premise Voyage=zforce withdrawn. Presence of input name cyttsp4_mt is
required; missing touch still fail-closes (interfaces → reboot). Host proves
source + voyage hardware RC; real framework ready remains device-side.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INITCHECK = ROOT / 'device/amazon/pw3/initcheck/InitCheck.cpp'
BOOTREPORT = ROOT / 'device/amazon/pw3/initcheck/BootReport.cpp'
BOOT_RC = ROOT / 'device/amazon/pw3/initcheck/pw3-boot-report.rc'
VOYAGE_HW = ROOT / 'tools/kernel-hardware/init.voyage.hardware.rc'


class VoyageInitcheckTouch(unittest.TestCase):
    def test_source_requires_cyttsp4_mt_only(self):
        text = INITCHECK.read_text(encoding='utf-8')
        self.assertIn('touch |= name=="cyttsp4_mt";', text)
        self.assertNotIn('zforce2', text)

    def test_bootreport_cyttsp_presence_not_zforce_sysfs(self):
        text = BOOTREPORT.read_text(encoding='utf-8')
        self.assertIn('cyttsp4_mt\\n', text)
        self.assertIn('cyttsp_idc', text)
        self.assertNotIn('zforce_connected', text)
        self.assertNotIn('zforce_init_stage', text)
        self.assertNotIn('FindZforceSysfs', text)

    def test_interfaces_failure_still_triggers_reboot_by_design(self):
        text = BOOT_RC.read_text(encoding='utf-8')
        self.assertIn('on property:sys.pw3.init_error=interfaces', text)
        self.assertIn('setprop sys.powerctl reboot,', text)

    def test_voyage_hardware_rc_loads_cyttsp_not_zforce(self):
        text = VOYAGE_HW.read_text(encoding='utf-8')
        self.assertIn('insmod /vendor/lib/modules/cyttsp4_core.ko', text)
        self.assertIn('insmod /vendor/lib/modules/cyttsp4_i2c.ko', text)
        self.assertIn('insmod /vendor/lib/modules/cyttsp4_mt_b.ko', text)
        self.assertIn('insmod /vendor/lib/modules/fsr_keypad.ko', text)
        self.assertIn('insmod /vendor/lib/modules/drv26xx_haptics.ko', text)
        self.assertNotIn('insmod /vendor/lib/modules/zforce', text)


if __name__ == '__main__':
    unittest.main()
