# SPDX-License-Identifier: Apache-2.0
"""Voyage handoff module must target stock vermagic, not android-core.

Real-device 2026-11-12T18:03:06: identity + install OK, then
  PW3_FIRST_KERNEL_CHECK_FAIL check=module_load errno=8 checks=42
Embedded .ko from E105-fix entry carried
  vermagic=3.0.35-lab126-voyage-android81 …
while stock Voyage uname release is 3.0.35-lab126. Stock defconfig has
CONFIG_MODVERSIONS=n, so the loader fail-closes on vermagic alone (ENOEXEC=8).
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / 'boot/profiles/voyage-5.13.6.json'
PW3 = ROOT / 'boot/profiles/pw3-5.16.2.1.1.json'
BUILD_MODULE = ROOT / 'boot/build_module.py'
HELPER_BUILT = Path(
    '/mnt/build-share/voyage-experimental-PRIVATE-offline-entry-modulefix-20261112'
    '/module/pw3_first_kernel.ko'
)
HELPER_BROKEN = Path(
    '/mnt/build-share/voyage-experimental-PRIVATE-offline-entry-e105fix-20261112'
    '/module/pw3_first_kernel.ko'
)


def vermagic_of(ko: bytes) -> str:
    at = ko.find(b'vermagic=')
    if at < 0:
        raise AssertionError('no vermagic=')
    end = ko.find(b'\0', at)
    return ko[at + len(b'vermagic='):end].decode('ascii')


class VoyageModuleVermagic(unittest.TestCase):
    def test_profile_points_at_stock_tree_not_android_core(self):
        p = json.loads(PROFILE.read_text())
        self.assertEqual(p['stock_kernel_release'], '3.0.35-lab126')
        self.assertEqual(p['module_kernel_source'], '/home/builder/pw3-build/linux-stock')
        self.assertEqual(p['module_kernel_output'], '/home/builder/pw3-build/out-stock-voyage')
        self.assertNotIn('android-core', p['module_kernel_source'])
        self.assertNotIn('android-core', p['module_kernel_output'])
        # Same split as PW3: stock tree for .ko, android zImage is a separate --kernel.
        pw3 = json.loads(PW3.read_text())
        self.assertEqual(pw3['module_kernel_source'], '/home/builder/pw3-build/linux-stock')

    def test_build_module_audits_vermagic_against_stock_release(self):
        text = BUILD_MODULE.read_text()
        self.assertIn('stock_kernel_release', text)
        self.assertIn('vermagic release is', text)
        self.assertIn('build against module_kernel_* stock tree', text)

    def test_broken_e105fix_ko_had_android81_vermagic(self):
        if not HELPER_BROKEN.is_file():
            self.skipTest('prior E105-fix .ko not on this host')
        verd = vermagic_of(HELPER_BROKEN.read_bytes())
        self.assertTrue(verd.startswith('3.0.35-lab126-voyage-android81'), verd)
        self.assertNotEqual(verd.split()[0], '3.0.35-lab126')

    def test_rebuilt_ko_matches_stock_release(self):
        if not HELPER_BUILT.is_file():
            self.skipTest('modulefix .ko not built yet on this host')
        verd = vermagic_of(HELPER_BUILT.read_bytes())
        self.assertEqual(verd.split()[0], '3.0.35-lab126', verd)
        self.assertRegex(verd, r'^3\.0\.35-lab126 preempt mod_unload ARMv7 p2v8')
        self.assertNotIn('android81', verd)


if __name__ == '__main__':
    unittest.main()
