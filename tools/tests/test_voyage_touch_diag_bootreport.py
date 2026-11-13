#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Host regression for Voyage BootReport H1/H2/H3 touch diagnosis (t160u).

Locks privacy and status semantics in source (and packed binary when present).
Does not claim device behavior.
"""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOTREPORT = ROOT / 'device/amazon/pw3/initcheck/BootReport.cpp'
SEPOLICY = ROOT / 'device/amazon/pw3/sepolicy/pw3_boot_report.te'
ZF_DRV = Path('/home/builder/pw3-build/linux-android-core/drivers/input/touchscreen/zforce2.c')
PACKED = Path('/tmp/sys-audit-zforce-touchdiag/pw3-boot-report')
SYSTEM_RAW = Path(
    '/mnt/build-share/voyage-experimental-PRIVATE-candidate-zforce-touchdiag-20261113/export/system.raw.img')
SYSTEM_RAW_FALLBACK = Path(
    '/mnt/build-share/voyage-experimental-PRIVATE-candidate-zforce-idc-20261112/export/system.raw.img')


class VoyageTouchDiagBootReport(unittest.TestCase):
    def test_source_reports_h1_h2_h3_fields(self):
        text = BOOTREPORT.read_text(encoding='utf-8')
        for needle in (
            'zforce_connected status=',
            'zforce_idc status=',
            'zforce_abs status=',
            'zforce_irq status=',
            'touch_evdev status=',
            'kTouchObserveMs = 1200',
            'status=absent',
            'return "eacces"',
            'status=ok value=',
            'syn_total=',
            'total_delta=',
        ):
            self.assertIn(needle, text)

    def test_source_never_grabs_or_logs_coordinates(self):
        text = BOOTREPORT.read_text(encoding='utf-8')
        # Comment may name EVIOCGRAB as forbidden; code must not call it.
        self.assertNotRegex(text, r'ioctl\s*\([^;]*EVIOCGRAB')
        self.assertNotIn('EVIOCSABS', text)
        # ABS ioctl for ranges only; event .value must not be reported.
        self.assertIn('EVIOCGABS(ABS_MT_POSITION_X)', text)
        self.assertIn('code/value discarded', text)
        self.assertNotIn('events[i].value', text)
        self.assertNotIn('events[i].code', text)

    def test_status_words_distinguish_missing_perm_and_real_zero(self):
        text = BOOTREPORT.read_text(encoding='utf-8')
        self.assertIn('ErrStatus', text)
        self.assertIn('ENOENT', text)
        self.assertIn('EACCES', text)
        # Real zero path for connected.
        self.assertIn('status=ok value=', text)
        # Real zero path for evdev counts stays status=ok with syn=0.
        self.assertIn('touch_evdev status=', text)

    def test_connected_discovers_real_sysfs_not_hardcoded_ready(self):
        text = BOOTREPORT.read_text(encoding='utf-8')
        self.assertIn('/sys/bus/platform/devices/', text)
        self.assertIn('zforce2', text)
        self.assertIn('/connected', text)
        self.assertNotIn('zforce_connected status=ok value=1', text)  # no hardcode
        if ZF_DRV.is_file():
            drv = ZF_DRV.read_text(encoding='utf-8', errors='replace')
            self.assertIn('DEVICE_ATTR(connected, 0444, zforce_connected_show, NULL)', drv)
            self.assertIn('.name = ZF_DRIVER_NAME', drv)

    def test_sepolicy_allows_readonly_input_and_idc(self):
        text = SEPOLICY.read_text(encoding='utf-8')
        self.assertIn('input_device:chr_file { getattr open read ioctl }', text)
        self.assertIn('r_dir_file(pw3_boot_report, system_file)', text)
        self.assertNotIn('input_device:chr_file { getattr open read write ioctl }', text)

    def test_alarm_covers_observe_window(self):
        text = BOOTREPORT.read_text(encoding='utf-8')
        self.assertIn('alarm(8)', text)
        self.assertIn('1.2s non-blocking touch observe', text)

    def test_packed_binary_embeds_new_field_tags_when_image_present(self):
        raw = SYSTEM_RAW if SYSTEM_RAW.is_file() else SYSTEM_RAW_FALLBACK
        if not raw.is_file():
            self.skipTest('system.raw not on host')
        PACKED.parent.mkdir(parents=True, exist_ok=True)
        if SYSTEM_RAW.is_file() or not PACKED.is_file():
            subprocess.run(
                ['debugfs', '-R', f'dump /bin/pw3-boot-report {PACKED}', str(raw)],
                check=True, capture_output=True)
        blob = PACKED.read_bytes()
        # Fallback idc image lacks new tags; only assert when touchdiag image exists.
        if SYSTEM_RAW.is_file():
            for tag in (b'zforce_connected', b'zforce_abs', b'touch_evdev', b'zforce_irq',
                        b'zforce_idc'):
                self.assertIn(tag, blob)
            self.assertNotIn(b'EVIOCGRAB', blob)


if __name__ == '__main__':
    unittest.main()
