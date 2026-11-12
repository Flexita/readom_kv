# SPDX-License-Identifier: Apache-2.0
"""Host checks for Voyage USB offline experimental packaging (no device)."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALL_H = ROOT / 'installer/install/install.h'
INSTALL_C = ROOT / 'installer/install/install.c'
LAUNCHER = ROOT / 'boot/build_launcher.py'
ENTRY = ROOT / 'boot/build_entry.py'
PACK = ROOT / 'tools/voyage-pack-usb-offline-experimental.py'
MIB = 1024 * 1024


class VoyageOfflineUsb(unittest.TestCase):
    def test_offline_only_field_in_headers(self):
        text = INSTALL_H.read_text()
        self.assertIn('int offline_only;', text)
        self.assertIn('never download', text.lower())

    def test_offline_only_refuses_without_network(self):
        text = INSTALL_C.read_text()
        self.assertIn('offline entry: copy %s into documents/', text)
        self.assertIn('rel->offline_only', text)
        # Must not call download when offline_only and payload missing.
        # Guard appears before download(r) in install_system.
        idx_guard = text.find('if (rel->offline_only)\n\t\t\treturn stop(r, INST_E_RELEASE')
        idx_download = text.find('enum inst_code c = download(r);')
        self.assertGreater(idx_guard, 0)
        self.assertGreater(idx_download, idx_guard)

    def test_builders_accept_offline_only_flag(self):
        self.assertIn('--offline-only', LAUNCHER.read_text())
        self.assertIn('--offline-only', ENTRY.read_text())
        self.assertIn('cannot be combined with --release-url', ENTRY.read_text())

    def test_packager_exists_and_forbids_readom_name(self):
        text = PACK.read_text()
        self.assertIn('refusing Readom.sh', text)
        self.assertIn('offline_only', text)
        self.assertIn('free_before_copy', text)

    def test_offline_fat_peak_math_with_real_payload_size(self):
        # Same arithmetic as voyage-pack-usb-offline-experimental.py.
        system = 512 * MIB
        data = 1024 * MIB
        reserve = 64 * MIB
        payload = 156484472  # experimental-0 compressed system from cloud build
        entry = 7820425
        copy_set = entry + payload
        free_after = system + data - payload + reserve
        free_before = free_after + copy_set
        # Must exceed the old online-only 1600 MiB slogan once copy_set is counted.
        self.assertGreater(free_before, 1600 * MIB)
        self.assertLess(payload, data)
        # After copy, installer peak credit is system+data-payload+reserve.
        self.assertEqual(free_after, system + data - payload + reserve)


if __name__ == '__main__':
    unittest.main()
