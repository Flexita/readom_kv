#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Lock Lab126 ZFStatus ordinals and BootComplete FORCE_RST paths (t166u).

Device report status=6 must not be read from truncated 0..4 docs.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HDR = Path('/home/builder/pw3-build/linux-android-core/drivers/input/touchscreen/zforceint2.h')
DRV = Path('/home/builder/pw3-build/linux-android-core/drivers/input/touchscreen/zforce2.c')
BOOT = ROOT / 'device/amazon/pw3/initcheck/BootReport.cpp'


class VoyageZforceInitStatusEnum(unittest.TestCase):
    def test_zfstatus_ordinal_six_is_err_force_rst(self):
        if not HDR.is_file():
            self.skipTest('zforceint2.h not on host')
        text = HDR.read_text(encoding='utf-8', errors='replace')
        m = re.search(
            r'typedef enum ZFStatus_e\s*\{(.*?)\}\s*ZFStatus;',
            text, re.S)
        self.assertIsNotNone(m)
        names = [n.strip().rstrip(',') for n in m.group(1).splitlines()
                 if n.strip() and not n.strip().startswith('/')
                 and not n.strip().startswith('*')]
        # Keep only enumerator identifiers (strip trailing comments).
        cleaned = []
        for n in names:
            tok = n.split()[0].rstrip(',')
            if tok.startswith('ZF_'):
                cleaned.append(tok)
        expected = [
            'ZF_OK', 'ZF_ERROR', 'ZF_TIMEOUT', 'ZF_IO_ERROR', 'ZF_NO_RESPONSE',
            'ZF_FORCE_EXIT', 'ZF_ERR_FORCE_RST', 'ZF_CONTINUE',
        ]
        self.assertEqual(cleaned, expected)
        self.assertEqual(cleaned[6], 'ZF_ERR_FORCE_RST')

    def test_bootcomplete_force_rst_only_from_processdata_i2c_frame(self):
        if not DRV.is_file():
            self.skipTest('zforce2.c not on host')
        text = DRV.read_text(encoding='utf-8', errors='replace')
        # getBootComplete: poll fail → ZF_ERROR; else processData result.
        self.assertRegex(text, r'if \(zforce_touch_poll\(\)\)\s*\n\s*return ZF_ERROR;')
        self.assertIn('processData(TYPE_BOOT_COMPLETE_RES, &result);', text)
        # Three I2C-frame FORCE_RST sites (header / start byte / body).
        self.assertEqual(text.count('*result = ZF_ERR_FORCE_RST;'), 3)
        # Parsed BootComplete with bad MCU bit → ZF_ERROR, not FORCE_RST.
        self.assertIn(
            '*result = ((res.comm_status & 0x1) == SUCCESS_RES) ? ZF_OK : ZF_ERROR;',
            text)
        # Stage 1 is set before getBootComplete.
        self.assertIn('zforce_init_stage = 1;', text)
        self.assertIn('if((status = getBootComplete()) != ZF_OK)', text)

    def test_bootreport_names_full_zfstatus_including_six(self):
        text = BOOT.read_text(encoding='utf-8')
        self.assertIn('ZF_ERR_FORCE_RST', text)
        self.assertIn('case 6: return "ZF_ERR_FORCE_RST"', text)
        self.assertIn('name=', text)
        # Must not document a truncated 0..4-only table as complete.
        self.assertIn('5 ZF_FORCE_EXIT', text)
        self.assertIn('6 ZF_ERR_FORCE_RST', text)
        self.assertIn('7 ZF_CONTINUE', text)


if __name__ == '__main__':
    unittest.main()
