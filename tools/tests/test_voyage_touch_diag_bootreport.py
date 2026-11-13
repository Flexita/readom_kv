#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""BootReport Cypress presence tags (t172u) — not zforce sysfs diagnostics."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOTREPORT = ROOT / 'device/amazon/pw3/initcheck/BootReport.cpp'


class VoyageTouchDiagBootreport(unittest.TestCase):
    def test_source_has_cyttsp_idc_and_touch_tags(self):
        text = BOOTREPORT.read_text(encoding='utf-8')
        self.assertIn('cyttsp_idc', text)
        self.assertIn('/system/usr/idc/cyttsp4_mt.idc', text)
        self.assertIn('touch_abs', text)
        self.assertIn('touch_irq', text)
        self.assertIn('touch_evdev', text)
        self.assertIn('cyttsp4_mt\\n', text)
        self.assertNotIn('zforce_connected', text)
        self.assertNotIn('zforce_init_stage', text)
        self.assertNotIn('init_i2c_fault', text)

    def test_idc_report_not_claimed_as_inputreader(self):
        text = BOOTREPORT.read_text(encoding='utf-8')
        self.assertIn('not a live InputReader probe', text)
        self.assertIn('source=file class=', text)


if __name__ == '__main__':
    unittest.main()
