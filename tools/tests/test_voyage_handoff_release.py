#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Voyage post-commit reboot: PreInit marker + handoff-init KERNEL_RELEASE.

Device log 20261112T183552 (module-fix entry d77a8a8e…): commit-before-kernel
present, no commit-return; no Android start wrote the report area; plant count
unchanged; reboot to stock with system/data kept. Host packaging of that entry
embedded:
  - pw3-testfile-init.real with strstr needle "-pw3-android81\\0"
  - pw3-handoff-init with hardcoded "3.0.35-lab126-pw3-android81"
while pw3-preinit.conf and android-core kernel.release are
"3.0.35-lab126-voyage-android81". PreInit parse_config then fails before
report_node is set → stop() → sleep → reboot(RB_AUTOBOOT).
"""
from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREINIT = ROOT / 'device/amazon/pw3/preinit/PreInit.c'
BUILD_ENTRY = ROOT / 'boot/build_entry.py'
HANDOFF_INIT = ROOT / 'boot/handoff-init/pw3-handoff-init.c'
VOYAGE_CFG = ROOT / 'config/models/voyage.config'
KERNEL_RELEASE_FILE = Path('/mnt/build-share/android-core-kernel-voyage/kernel.release')
PACKED_INITRAMFS = Path(
    '/mnt/build-share/voyage-experimental-PRIVATE-offline-entry-modulefix-20261112'
    '/public-initramfs.cpio.gz')
NEW_INITRAMFS = Path(
    '/mnt/build-share/voyage-experimental-PRIVATE-offline-entry-preinitfix-20261112'
    '/public-initramfs.cpio.gz')


def load_pack():
    import sys
    spec = importlib.util.spec_from_file_location(
        'pack_handoff_release', ROOT / 'tools/preinit-pack/pack.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class VoyageHandoffRelease(unittest.TestCase):
    def test_preinit_source_uses_model_neutral_android81_marker(self):
        text = PREINIT.read_text(encoding='utf-8')
        self.assertIn('strstr(eq, "-android81")', text)
        self.assertNotIn('strstr(eq, "-pw3-android81")', text)

    def test_voyage_localversion_is_voyage_android81(self):
        text = VOYAGE_CFG.read_text(encoding='utf-8')
        self.assertIn('CONFIG_LOCALVERSION="-lab126-voyage-android81"', text)

    def test_build_entry_defines_kernel_release_from_argument(self):
        text = BUILD_ENTRY.read_text(encoding='utf-8')
        self.assertIn('def boot_programs(work, kernel_release)', text)
        self.assertIn('-DKERNEL_RELEASE="%s"', text)
        self.assertIn("boot_programs(work, release)", text)
        self.assertIn("b'-pw3-android81\\0'", text)
        self.assertIn("b'-android81\\0'", text)

    def test_handoff_init_default_remains_overridable(self):
        text = HANDOFF_INIT.read_text(encoding='utf-8')
        self.assertIn('#ifndef KERNEL_RELEASE', text)
        self.assertIn('#define KERNEL_RELEASE "3.0.35-lab126-pw3-android81"', text)

    def test_android_core_kernel_release_is_voyage(self):
        if not KERNEL_RELEASE_FILE.is_file():
            self.skipTest('android-core kernel.release not on this host')
        release = KERNEL_RELEASE_FILE.read_text(encoding='utf-8').strip()
        self.assertEqual(release, '3.0.35-lab126-voyage-android81')
        self.assertIn('-android81', release)
        self.assertNotIn('-pw3-android81', release)

    def test_broken_modulefix_initramfs_had_pw3_only_needles(self):
        if not PACKED_INITRAMFS.is_file():
            self.skipTest('module-fix initramfs not on this host')
        pack = load_pack()
        by_name = {e.name: e for e in pack.read_ramdisk(PACKED_INITRAMFS)}
        storage = by_name['pw3-testfile-init.real'].data
        handoff = by_name['pw3-testfile-init'].data
        self.assertIn(b'-pw3-android81\0', storage)
        self.assertIn(b'3.0.35-lab126-pw3-android81', handoff)
        self.assertNotIn(b'3.0.35-lab126-voyage-android81', handoff)

    def test_rebuilt_initramfs_matches_voyage_release(self):
        if not NEW_INITRAMFS.is_file():
            self.skipTest('preinit-fix initramfs not built yet')
        pack = load_pack()
        by_name = {e.name: e for e in pack.read_ramdisk(NEW_INITRAMFS)}
        storage = by_name['pw3-testfile-init.real'].data
        handoff = by_name['pw3-testfile-init'].data
        self.assertNotIn(b'-pw3-android81\0', storage)
        self.assertIn(b'-android81\0', storage)
        self.assertIn(b'3.0.35-lab126-voyage-android81', handoff)
        self.assertNotIn(b'3.0.35-lab126-pw3-android81', handoff)


if __name__ == '__main__':
    unittest.main()
