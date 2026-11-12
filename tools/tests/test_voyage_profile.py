# SPDX-License-Identifier: Apache-2.0
"""The Voyage profile cannot be installed, and it is not the PW3 record renamed."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_module():
    path = ROOT / 'tools/voyage_profile.py'
    spec = importlib.util.spec_from_file_location('voyage_profile', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VoyageProfile(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        self.voyage = self.mod.load(self.mod.VOYAGE_PROFILE)
        self.pw3 = self.mod.load(self.mod.PW3_PROFILE)
        self.text = self.mod.VOYAGE_PROFILE.read_text()

    def test_the_committed_profile_cannot_be_built(self):
        found = self.mod.problems(self.voyage, self.pw3)
        self.assertIn('installable is not true', found)
        self.assertIn('identity_ready is not true', found)
        self.assertIn('device_confirmed is not true', found)
        with self.assertRaises(SystemExit):
            self.mod.refuse_unless_installable(self.mod.VOYAGE_PROFILE)

    def test_the_historical_pw3_profile_cannot_be_built_either(self):
        self.assertIs(self.pw3.get('installable'), False)
        with self.assertRaises(SystemExit):
            self.mod.refuse_unless_installable(self.mod.PW3_PROFILE)

    def test_qemu_is_not_treated_as_a_device(self):
        self.assertEqual(self.mod.problems({'module_profile': 2}), [])

    def test_pw3_handoff_constants_are_not_in_the_voyage_profile(self):
        self.assertNotIn(self.mod.PW3_EIPS_SHA256, self.text)
        self.assertNotIn(self.pw3['stock_kernel_version'], self.text)
        self.assertNotIn(self.pw3['cmdline_base'], self.text)
        for name, body in self.pw3['stock_functions'].items():
            self.assertNotIn(body['sha256'], self.text, name)

    def test_filling_the_blanks_with_the_pw3_record_still_refuses(self):
        forged = json.loads(self.text)
        forged['installable'] = True
        forged['identity_ready'] = True
        forged['device_confirmed'] = True
        forged['measured'] = {
            'eips_sha256': self.mod.PW3_EIPS_SHA256,
            'eips_bytes': 62176,
            'uname_release': self.pw3['stock_kernel_release'],
            'uname_version': self.pw3['stock_kernel_version'],
            'machine_id': self.pw3['machine'],
            'stock_cmdline': self.pw3['cmdline_base'],
            'ram': self.pw3['ram'],
            'partition_table': {'copied': True},
            'stock_functions': self.pw3['stock_functions'],
        }
        found = self.mod.problems(forged, self.pw3)
        self.assertTrue(any('Paperwhite 3' in item for item in found), found)

    def test_source_lock_matches_the_profile(self):
        lock = json.loads((ROOT / 'source-lock.json').read_text())['voyage_kernel']
        source = self.voyage['source']
        for key in ('archive_sha256', 'member_sha256', 'firmware_sha256',
                    'archive_bytes', 'member_bytes', 'firmware_bytes'):
            self.assertEqual(source[key], lock[key], key)
        self.assertEqual(source['patches_applied'], 85)
        self.assertEqual(source['patches_failed'], 0)

    def test_source_verified_shared_values_are_not_refused(self):
        """4091 and 3.0.35-lab126 are in the Voyage GPL tree, not only on the PW3."""
        ready = json.loads(self.text)
        ready['installable'] = True
        ready['identity_ready'] = True
        ready['device_confirmed'] = True
        ready['measured'] = {
            'eips_sha256': 'a' * 64,
            'eips_bytes': 1,
            'uname_release': self.mod.SOURCE_SHARED_KERNEL_RELEASE,
            'uname_version': '#1 PREEMPT Thu Jan 1 00:00:00 UTC 2015',
            'machine_id': self.mod.SOURCE_SHARED_MACHINE_ID,
            'stock_cmdline': 'console=ttymxc0,115200 quiet',
            'ram': self.pw3['ram'],
            'partition_table': {'read_from': '/proc/partitions on the device'},
            'stock_functions': {'pm_test_show': {'bytes': 4, 'sha256': 'b' * 64}},
        }
        self.assertEqual(ready['measured']['machine_id'], self.pw3['machine'])
        self.assertEqual(self.mod.problems(ready, self.pw3), [])

    def test_a_complete_reading_that_is_not_the_pw3_record_would_build(self):
        """The gate is fail-closed, not sealed: a real device reading can pass."""
        ready = json.loads(self.text)
        ready['installable'] = True
        ready['identity_ready'] = True
        ready['device_confirmed'] = True
        ready['measured'] = {
            'eips_sha256': 'a' * 64,
            'eips_bytes': 1,
            'uname_release': '3.0.35-lab126',
            'uname_version': '#1 PREEMPT Thu Jan 1 00:00:00 UTC 2015',
            'machine_id': 1,
            'stock_cmdline': 'console=ttymxc0,115200',
            'ram': [['0x80000000', '0x20000000']],
            'partition_table': {'read_from': '/proc/partitions on the device'},
            'stock_functions': {'pm_test_show': {'bytes': 1, 'sha256': 'b' * 64}},
        }
        self.assertEqual(self.mod.problems(ready, self.pw3), [])


if __name__ == '__main__':
    unittest.main()
