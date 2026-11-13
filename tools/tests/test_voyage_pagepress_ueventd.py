#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""t175u: DAC/ueventd packaging locks that independent audit found missing.

These tests fail on the t174u omission pattern:
- system image only shipping fb0 in ueventd.pw3.fragment.rc
- CHANGE-AUDIT claiming ramdisk rules without entry+vendor load paths
- no post-insmod chmod/chown/restorecon for late misc nodes
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRAGMENT = ROOT / 'tools/kernel-hardware/ueventd.pw3.fragment.rc'
VENDOR_UEVENTD = ROOT / 'device/amazon/pw3/rootdir/ueventd.vendor.rc'
RAMDISK_UEVENTD = ROOT / 'device/amazon/pw3/rootdir/ueventd.pw3.rc'
RC = ROOT / 'tools/kernel-hardware/init.voyage.hardware.rc'
VOYAGE_MK = ROOT / 'device/amazon/voyage/voyage.mk'
FILE_CONTEXTS = ROOT / 'device/amazon/pw3/sepolicy/file_contexts'
FSR_C = ROOT / 'device/amazon/pw3/input/FsrEnable.c'
BOOT = ROOT / 'device/amazon/pw3/initcheck/BootReport.cpp'
FSR_TE = ROOT / 'device/amazon/pw3/sepolicy/pw3_fsr_enable.te'


class VoyagePagepressUeventd(unittest.TestCase):
    def test_fragment_has_keypad_and_als_not_only_fb0(self):
        text = FRAGMENT.read_text(encoding='utf-8')
        self.assertIn('/dev/graphics/fb0', text)
        self.assertIn('/dev/keypad 0660 system system', text)
        self.assertIn('/dev/als 0660 system system', text)
        # Guard the exact t174u audit miss: fragment must not be fb0-only.
        nodes = [l for l in text.splitlines() if l.strip().startswith('/dev/')]
        self.assertGreaterEqual(len(nodes), 3)

    def test_vendor_ueventd_rc_has_keypad_als(self):
        text = VENDOR_UEVENTD.read_text(encoding='utf-8')
        self.assertIn('/dev/keypad 0660 system system', text)
        self.assertIn('/dev/als 0660 system system', text)
        # Never widen to world-writable.
        for line in text.splitlines():
            if '/dev/keypad' in line or '/dev/als' in line:
                self.assertIn('0660', line)
                self.assertNotIn('0666', line)

    def test_voyage_mk_installs_vendor_ueventd_rc(self):
        text = VOYAGE_MK.read_text(encoding='utf-8')
        self.assertIn('ueventd.vendor.rc:$(TARGET_COPY_OUT_VENDOR)/ueventd.rc', text)

    def test_ramdisk_ueventd_still_has_keypad_als(self):
        text = RAMDISK_UEVENTD.read_text(encoding='utf-8')
        self.assertIn('/dev/keypad 0660 system system', text)
        self.assertIn('/dev/als 0660 system system', text)

    def test_post_insmod_reasserts_dac_and_restorecon(self):
        text = RC.read_text(encoding='utf-8')
        # Order: insmod fsr/als before chmod/restorecon/start enable.
        fsr = text.index('insmod /vendor/lib/modules/fsr_keypad.ko')
        als = text.index('insmod /vendor/lib/modules/als_max44009.ko')
        chmod_k = text.index('chmod 0660 /dev/keypad')
        chown_k = text.index('chown system system /dev/keypad')
        restore_k = text.index('restorecon /dev/keypad')
        chmod_a = text.index('chmod 0660 /dev/als')
        restore_a = text.index('restorecon /dev/als')
        enable = text.index('start pw3-fsr-enable')
        self.assertLess(fsr, chmod_k)
        self.assertLess(als, chmod_a)
        self.assertLess(chown_k, restore_k)
        self.assertLess(restore_k, enable)
        self.assertLess(restore_a, enable)
        body = '\n'.join(l for l in text.splitlines() if not l.lstrip().startswith('#'))
        self.assertNotIn('chmod 0666', body)
        self.assertNotIn('setenforce', body)
        self.assertNotIn('permissive', body)

    def test_file_contexts_label_keypad_and_als(self):
        text = FILE_CONTEXTS.read_text(encoding='utf-8')
        self.assertIn('/dev/keypad', text)
        self.assertIn('input_device', text)
        self.assertIn('/dev/als', text)
        self.assertIn('sensors_device', text)

    def test_fsr_enable_publishes_errno_property(self):
        text = FSR_C.read_text(encoding='utf-8')
        self.assertIn('sys.pw3.fsr.enable', text)
        self.assertIn('open_errno=', text)
        self.assertIn('errno=', text)
        self.assertIn('property_set', text)

    def test_bootreport_emits_devnode_and_enable_status(self):
        text = BOOT.read_text(encoding='utf-8')
        self.assertIn('DevNodeMeta', text)
        self.assertIn('pagepress_enable', text)
        self.assertIn('sys.pw3.fsr.enable', text)
        self.assertIn('devnode path=', text)

    def test_fsr_sepolicy_allows_boot_prop_not_global(self):
        text = FSR_TE.read_text(encoding='utf-8')
        self.assertIn('set_prop(pw3_fsr_enable, pw3_boot_prop)', text)
        self.assertNotIn('permissive', text)
        body = '\n'.join(l for l in text.splitlines() if not l.strip().startswith('#'))
        self.assertNotIn('allow pw3_fsr_enable self:capability', body)


if __name__ == '__main__':
    unittest.main()
