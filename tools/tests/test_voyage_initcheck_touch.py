#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Voyage initcheck touch name vs PW3 cyttsp residue.

printk recapture (voyage-printk-recapture-v1) kept:
  pw3-init-check: real interfaces not ready: display=1 power_key=1 touch=0;
  framework remains stopped
together with PreInit reaching "executing the original AOSP init" and storage
check passing. Rebuilt system.img's /bin/pw3-init-check embeds both
cyttsp4_mt and zforce2; Voyage loads zforce2 (ZF_INPUT_NAME \"zforce2\").
Missing touch still fail-closes (interfaces → reboot). Host proves binary
strings + source; real Voyage zforce2 probe and first framework ready are
still device-side evidence.
"""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INITCHECK = ROOT / 'device/amazon/pw3/initcheck/InitCheck.cpp'
BOOTREPORT = ROOT / 'device/amazon/pw3/initcheck/BootReport.cpp'
BOOT_RC = ROOT / 'device/amazon/pw3/initcheck/pw3-boot-report.rc'
VOYAGE_HW = ROOT / 'tools/kernel-hardware/init.voyage.hardware.rc'
ZF_HDR = Path('/home/builder/pw3-build/linux-android-core/drivers/input/touchscreen/zforceint2.h')
PACKED_INITCHECK = Path('/tmp/sys-audit-zforce/pw3-init-check')
PACKED_BOOTREPORT = Path('/tmp/sys-audit-zforce/pw3-boot-report')
PACKED_BOOT_RC = Path('/tmp/sys-audit-zforce/pw3-boot-report.rc')
PACKED_VOYAGE_HW = Path('/tmp/sys-audit-zforce/init.voyage.hardware.rc')
SYSTEM_RAW = Path(
    '/mnt/build-share/voyage-experimental-PRIVATE-candidate-zforce-20261112/export/system.raw.img')


def ensure_packed_extracts():
    needed = (PACKED_INITCHECK, PACKED_BOOTREPORT, PACKED_BOOT_RC, PACKED_VOYAGE_HW)
    if all(p.is_file() for p in needed):
        return
    if not SYSTEM_RAW.is_file():
        raise unittest.SkipTest('packed system.raw.img not on this host')
    PACKED_INITCHECK.parent.mkdir(parents=True, exist_ok=True)
    for src, dst in (
        ('/bin/pw3-init-check', PACKED_INITCHECK),
        ('/bin/pw3-boot-report', PACKED_BOOTREPORT),
        ('/etc/init/pw3-boot-report.rc', PACKED_BOOT_RC),
        ('/vendor/etc/init/init.voyage.hardware.rc', PACKED_VOYAGE_HW),
    ):
        subprocess.run(
            ['debugfs', '-R', f'dump {src} {dst}', str(SYSTEM_RAW)],
            check=True, capture_output=True)


class VoyageInitcheckTouch(unittest.TestCase):
    def test_source_accepts_zforce2_and_keeps_pw3_cyttsp(self):
        text = INITCHECK.read_text(encoding='utf-8')
        self.assertIn('cyttsp4_mt', text)
        self.assertIn('zforce2', text)
        self.assertIn('name=="cyttsp4_mt" || name=="zforce2"', text)
        # Must not be cyttsp-only anymore.
        self.assertNotIn('touch |= name=="cyttsp4_mt";', text)

    def test_bootreport_accepts_zforce2(self):
        text = BOOTREPORT.read_text(encoding='utf-8')
        self.assertIn('cyttsp4_mt\\n', text)
        self.assertIn('zforce2\\n', text)

    def test_interfaces_failure_still_triggers_reboot_by_design(self):
        text = BOOT_RC.read_text(encoding='utf-8')
        self.assertIn('on property:sys.pw3.init_error=interfaces', text)
        self.assertIn('setprop sys.powerctl reboot,', text)

    def test_voyage_hardware_rc_loads_zforce_not_cyttsp(self):
        text = VOYAGE_HW.read_text(encoding='utf-8')
        self.assertIn('insmod /vendor/lib/modules/zforce2.ko', text)
        self.assertIn('insmod /vendor/lib/modules/fsr_keypad.ko', text)
        # Comment may mention cyttsp4; must not load it.
        self.assertNotIn('insmod /vendor/lib/modules/cyttsp', text)

    def test_kernel_zf_input_name_is_zforce2(self):
        if not ZF_HDR.is_file():
            self.skipTest('android-core zforce header not on this host')
        text = ZF_HDR.read_text(encoding='utf-8', errors='replace')
        self.assertIn('#define ZF_INPUT_NAME               "zforce2"', text)

    def test_packed_initcheck_and_bootreport_accept_zforce2(self):
        ensure_packed_extracts()
        init_blob = PACKED_INITCHECK.read_bytes()
        self.assertIn(b'cyttsp4_mt', init_blob)
        self.assertIn(b'zforce2', init_blob)
        boot_blob = PACKED_BOOTREPORT.read_bytes()
        self.assertIn(b'cyttsp4_mt', boot_blob)
        self.assertIn(b'zforce2', boot_blob)
        rc = PACKED_BOOT_RC.read_text(encoding='utf-8')
        self.assertIn('on property:sys.pw3.init_error=interfaces', rc)
        self.assertIn('setprop sys.powerctl reboot,', rc)
        hw = PACKED_VOYAGE_HW.read_text(encoding='utf-8')
        self.assertIn('zforce2.ko', hw)
        self.assertNotIn('insmod /vendor/lib/modules/cyttsp', hw)


if __name__ == '__main__':
    unittest.main()
