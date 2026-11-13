#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Host locks for t174u PagePress enable + ALS packaging (not device success)."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RC = ROOT / 'tools/kernel-hardware/init.voyage.hardware.rc'
EXPORT = ROOT / 'tools/kernel-hardware/export_component.py'
VOYAGE_MK = ROOT / 'device/amazon/voyage/voyage.mk'
FSR_C = ROOT / 'device/amazon/pw3/input/FsrEnable.c'
FSR_KL = ROOT / 'device/amazon/pw3/input/fsr_keypad.kl'
SENSORS = ROOT / 'device/amazon/pw3/sensors/sensors.c'
OVERLAY = ROOT / 'device/amazon/voyage/overlay/frameworks/base/core/res/res/values/config.xml'
BOOT = ROOT / 'device/amazon/pw3/initcheck/BootReport.cpp'
FSR_DRV = Path('/home/builder/pw3-build/linux-android-core/drivers/input/keyboard/fsr_keypad.c')


class VoyagePagepressAls(unittest.TestCase):
    def test_voyage_rc_loads_als_and_starts_fsr_enable(self):
        text = RC.read_text(encoding='utf-8')
        self.assertIn('insmod /vendor/lib/modules/als_max44009.ko', text)
        self.assertIn('insmod /vendor/lib/modules/fsr_keypad.ko', text)
        self.assertIn('start pw3-fsr-enable', text)
        for line in text.splitlines():
            if line.strip().startswith('insmod'):
                self.assertNotIn('zforce2', line)

    def test_exporter_includes_als_and_boot_order(self):
        text = EXPORT.read_text(encoding='utf-8')
        self.assertIn("'als_max44009'", text)
        self.assertIn("'CONFIG_INPUT_ALS_MAX44009':'m'", text)
        self.assertIn(
            "['drv26xx_haptics','fsr_keypad','als_max44009',"
            "'cyttsp4_core','cyttsp4_i2c','cyttsp4_mt_b','cfg80211']",
            text,
        )

    def test_fsr_enable_uses_event_enable_ioctl_only(self):
        text = FSR_C.read_text(encoding='utf-8')
        self.assertIn('KEYPAD_IOCTL_EVENT_ENABLE', text)
        self.assertIn('/dev/keypad', text)
        body = '\n'.join(
            l for l in text.splitlines()
            if not l.strip().startswith('*') and not l.strip().startswith('/*'))
        self.assertNotIn('TOUCH_ACTIVE', body)
        self.assertEqual(body.count('ioctl('), 1)

    def test_fsr_kl_maps_page_to_volume(self):
        text = FSR_KL.read_text(encoding='utf-8')
        self.assertIn('key 104   VOLUME_UP', text)
        self.assertIn('key 109   VOLUME_DOWN', text)

    def test_sensors_hal_reads_real_lux_ioctl(self):
        text = SENSORS.read_text(encoding='utf-8')
        self.assertIn('ALS_IOCTL_GET_LUX', text)
        self.assertIn('SENSOR_TYPE_LIGHT', text)
        body = '\n'.join(l for l in text.splitlines() if not l.strip().startswith('*') and not l.strip().startswith('/*'))
        self.assertNotIn('ALS_IOCTL_AUTOMODE', body)
        self.assertNotIn('ALS_IOCTL_WRITE_REG', body)

    def test_voyage_overlay_enables_auto_brightness_with_curves(self):
        text = OVERLAY.read_text(encoding='utf-8')
        self.assertIn('config_automatic_brightness_available">true', text)
        self.assertIn('config_autoBrightnessLevels', text)
        self.assertIn('config_autoBrightnessLcdBacklightValues', text)
        self.assertIn('config_autoBrightnessDarkeningLightDebounce', text)

    def test_voyage_mk_packages_sensors_and_fsr(self):
        text = VOYAGE_MK.read_text(encoding='utf-8')
        self.assertIn('pw3-fsr-enable', text)
        self.assertIn('sensors.pw3', text)
        self.assertIn('android.hardware.sensors@1.0-service', text)
        self.assertIn('android.hardware.sensor.light.xml', text)
        self.assertIn('fsr_keypad.kl', text)

    def test_bootreport_observes_pagepress_and_als(self):
        text = BOOT.read_text(encoding='utf-8')
        self.assertIn('pagepress=', text)
        self.assertIn('als_lux', text)
        self.assertIn('fsr_keypad', text)

    def test_fsr_driver_still_defaults_event_enable_false(self):
        """Stock probe stays false; userspace oneshot enables — not a kernel flip."""
        if not FSR_DRV.is_file():
            self.skipTest('fsr_keypad.c not on host')
        text = FSR_DRV.read_text(encoding='utf-8', errors='replace')
        self.assertIn('g_keypad.event_enable = false;', text)


if __name__ == '__main__':
    unittest.main()
