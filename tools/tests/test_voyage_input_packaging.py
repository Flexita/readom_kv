#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Static Voyage input packaging — Cypress cyttsp4 (t172u/t174u).

Does not claim device hardware behavior. Voyage loads cyttsp4_core→i2c→mt_b
plus PagePress/haptics/ALS; must not load zforce2. cyttsp4_mt.idc remains the
touchScreen class file. FSR probe still defaults event_enable=false; userspace
pw3-fsr-enable flips it after insmod.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CYT_SRC = ROOT / 'device/amazon/pw3/input/cyttsp4_mt.idc'
PW3_MK = ROOT / 'device/amazon/pw3/pw3.mk'
VOYAGE_HW = ROOT / 'tools/kernel-hardware/init.voyage.hardware.rc'
EXPORT = ROOT / 'tools/kernel-hardware/export_component.py'
FSR_C = Path('/home/builder/pw3-build/linux-android-core/drivers/input/keyboard/fsr_keypad.c')
INPUT_READER = Path(
    '/home/builder/android-src/frameworks/native/services/inputflinger/InputReader.cpp')


class VoyageInputPackaging(unittest.TestCase):
    def test_source_ships_cyttsp4_mt_idc_as_touchscreen(self):
        self.assertTrue(CYT_SRC.is_file())
        text = CYT_SRC.read_text()
        self.assertIn('touch.deviceType = touchScreen', text)
        self.assertIn('device.internal = 1', text)
        mk = PW3_MK.read_text()
        self.assertIn('cyttsp4_mt.idc:system/usr/idc/cyttsp4_mt.idc', mk)

    def test_voyage_hw_loads_cyttsp_fsr_haptics_als_not_zforce(self):
        text = VOYAGE_HW.read_text()
        self.assertIn('insmod /vendor/lib/modules/cyttsp4_core.ko', text)
        self.assertIn('insmod /vendor/lib/modules/cyttsp4_i2c.ko', text)
        self.assertIn('insmod /vendor/lib/modules/cyttsp4_mt_b.ko', text)
        self.assertIn('insmod /vendor/lib/modules/fsr_keypad.ko', text)
        self.assertIn('insmod /vendor/lib/modules/drv26xx_haptics.ko', text)
        self.assertIn('insmod /vendor/lib/modules/als_max44009.ko', text)
        self.assertIn('start pw3-fsr-enable', text)
        self.assertNotIn('insmod /vendor/lib/modules/zforce', text)

    def test_exporter_voyage_modules_are_cyttsp_not_zforce(self):
        text = EXPORT.read_text()
        self.assertIn("'cyttsp4_mt_b'", text)
        # Voyage map must include cyttsp and must not list zforce2 path.
        start = text.index('VOYAGE_TOUCH_MODULES={')
        end = text.index('}', start)
        block = text[start:end]
        self.assertIn('cyttsp4_core', block)
        self.assertIn('fsr_keypad', block)
        self.assertIn('als_max44009', block)
        self.assertNotIn('zforce2', block)

    def test_inputreader_defaults_unknown_mt_to_pointer_without_idc(self):
        if not INPUT_READER.is_file():
            self.skipTest('AOSP InputReader.cpp not on host')
        text = INPUT_READER.read_text()
        self.assertIn('The device is a touch pad of unknown purpose.', text)
        self.assertIn('mParameters.deviceType = Parameters::DEVICE_TYPE_POINTER;', text)
        self.assertIn('touch.deviceType', text)
        self.assertIn('DEVICE_TYPE_TOUCH_SCREEN', text)

    def test_fsr_defaults_event_enable_false(self):
        if not FSR_C.is_file():
            self.skipTest('fsr_keypad.c not on host')
        text = FSR_C.read_text()
        self.assertIn('g_keypad.event_enable = false;', text)
        self.assertIn('KEYPAD_IOCTL_EVENT_ENABLE', text)

    def test_voyage_boot_order_cyttsp_after_pagepress(self):
        text = EXPORT.read_text()
        self.assertIn(
            "['drv26xx_haptics','fsr_keypad','als_max44009',"
            "'cyttsp4_core','cyttsp4_i2c','cyttsp4_mt_b','cfg80211']",
            text)


if __name__ == '__main__':
    unittest.main()
