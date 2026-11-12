# SPDX-License-Identifier: Apache-2.0
"""The Voyage profile cannot be installed, and it is not the PW3 record renamed."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

STOCK_FUNCTION_SHA256 = {
    'pm_test_show': '71025c707238a74117fc7a7065546f17efa057bb3084f17bdfe048d878543074',
    'l2x0_flush_all': '5879a00e18ecd63fcb974d2a93a3d193092213037d2a10cb64a381a8f7350131',
    'l2x0_disable': '2fb38c26df26f978137ab7e84c60f57af8ff41e25170af0a6dc09be17e0dd9f9',
    'l2x0_inv_all': 'b38adb741635cfd2ddf38549cbf23c1d7246073b403528539335d72d2fe3368a',
}
STOCK_FUNCTION_BYTES = {
    'pm_test_show': 124,
    'l2x0_flush_all': 116,
    'l2x0_disable': 124,
    'l2x0_inv_all': 152,
}
VOYAGE_CMDLINE = (
    'rootwait log_pos_goal=0x8fff0000 console=ttymxc0,115200 '
    'root=/dev/mmcblk0p1 ro ip=off quiet video=mxcepdcfb:E60,bpp=8,x_mem=3M'
)


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
        self.assertNotIn('measured.machine_id is empty', found)
        with self.assertRaises(SystemExit):
            self.mod.refuse_unless_installable(self.mod.VOYAGE_PROFILE)

    def test_machine_pin_is_source_proven_not_measured(self):
        self.assertEqual(self.voyage['machine'], 4091)
        self.assertEqual(self.voyage['source']['stock_machine_desc_nr'], 4091)
        self.assertIsNone(self.voyage['measured']['machine_id'])
        self.assertEqual(
            self.voyage['source']['stock_machine_desc_name'],
            'Freescale i.MX 6SoloLite based Wario Board')

    def test_inventing_a_measured_machine_id_is_refused(self):
        forged = json.loads(self.text)
        forged['installable'] = True
        forged['identity_ready'] = True
        forged['device_confirmed'] = True
        # Give bootmode=main so this case isolates the machine_id forgery.
        forged['device_probe_extra']['bootmode'] = 'main'
        forged['measured']['machine_id'] = 4091
        found = self.mod.problems(forged, self.pw3)
        self.assertTrue(any('measured.machine_id must stay null' in i for i in found), found)

    def test_empty_bootmode_blocks_opening_gates(self):
        forged = json.loads(self.text)
        forged['installable'] = True
        forged['identity_ready'] = True
        forged['device_confirmed'] = True
        # Isolate the historical empty extra-probe reading.
        forged['measured'].pop('bootmode', None)
        forged['device_probe_extra']['bootmode'] = ''
        found = self.mod.problems(forged, self.pw3)
        self.assertTrue(
            any('bootmode reading is empty' in i for i in found), found)
        self.assertTrue(
            any('root=mmcblk0p1 does not substitute' in i for i in found), found)

    def test_root_partition_does_not_imply_bootmode_main(self):
        """cmdline root=/dev/mmcblk0p1 is already measured; that is not bootmode."""
        self.assertIn('root=/dev/mmcblk0p1', self.voyage['measured']['stock_cmdline'])
        self.assertEqual(self.voyage['device_probe_extra']['bootmode'], '')
        ready = json.loads(self.text)
        ready['installable'] = True
        ready['identity_ready'] = True
        ready['device_confirmed'] = True
        ready['measured'].pop('bootmode', None)
        found = self.mod.problems(ready, self.pw3)
        self.assertTrue(any('bootmode reading is empty' in i for i in found), found)

    def test_bootmode_main_is_required_not_diags(self):
        forged = json.loads(self.text)
        forged['installable'] = True
        forged['identity_ready'] = True
        forged['device_confirmed'] = True
        forged['measured'].pop('bootmode', None)
        forged['device_probe_extra']['bootmode'] = 'diags'
        found = self.mod.problems(forged, self.pw3)
        self.assertTrue(any("bootmode reading is 'diags'" in i for i in found), found)

    def test_bootmode_main_does_not_auto_open_installable(self):
        """A verified main reading fills that gate only; flags stay closed."""
        self.assertEqual(self.voyage['measured']['bootmode'], 'main')
        self.assertEqual(
            self.voyage['device_probe_bootmode']['sha256'],
            'eb98afc157f42877c40ea9032dd06ce23475dcb635c83a5a325c49645eb0292e')
        self.assertEqual(self.voyage['device_probe_bootmode']['bytes'], 337)
        self.assertEqual(self.voyage['device_probe_bootmode']['bootmode'], 'main')
        self.assertEqual(self.voyage['device_probe_bootmode']['result'], 'ok')
        self.assertIs(self.voyage['installable'], False)
        self.assertIs(self.voyage['identity_ready'], False)
        self.assertIs(self.voyage['device_confirmed'], False)
        found = self.mod.problems(self.voyage, self.pw3)
        self.assertIn('installable is not true', found)
        self.assertIn('identity_ready is not true', found)
        self.assertIn('device_confirmed is not true', found)
        self.assertFalse(any('bootmode' in i for i in found), found)

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
            'machine_id': None,
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

    def test_a_redacted_command_line_cannot_open_the_gate(self):
        ready = json.loads(self.text)
        ready['installable'] = True
        ready['identity_ready'] = True
        ready['device_confirmed'] = True
        ready['device_probe_extra']['bootmode'] = 'main'
        ready['measured'] = {
            'eips_sha256': 'a' * 64,
            'eips_bytes': 61104,
            'uname_release': '3.0.35-lab126',
            'uname_version': '#2 PREEMPT Thu Apr 8 09:39:57 UTC 2021',
            'machine_id': None,
            'stock_cmdline': 'log_pos_goal=[redacted] console=ttymxc0,115200 ro ip=[redacted] quiet',
            'ram': self.pw3['ram'],
            'partition_table': {'sysfs_ro': 0},
            'stock_functions': {'pm_test_show': {'bytes': 4, 'sha256': 'b' * 64}},
        }
        found = self.mod.problems(ready, self.pw3)
        self.assertIn('measured.stock_cmdline contains a redacted value', found)

    def test_probe_and_extra_probe_records(self):
        probe = self.voyage['device_probe']
        self.assertEqual(probe['sha256'],
                         'eab14ee928b2abaf6925d1fd2f04e461c1bc0525fef01a6cd5b9252b05864f15')
        self.assertEqual(probe['bytes'], 2195)
        self.assertEqual(probe['uid'], 0)
        extra = self.voyage['device_probe_extra']
        self.assertEqual(extra['sha256'],
                         '47a04517af9e353643eaa98aba484ab4ea34adb899f3b49b6be79b4604e5a4ed')
        self.assertEqual(extra['bytes'], 1779)
        self.assertEqual(extra['uid'], 0)
        self.assertEqual(extra['result'], 'partial')
        self.assertEqual(extra['errors'], 1)
        self.assertEqual(extra['bootmode'], '')
        self.assertEqual(extra['machine_id'], 'not collected')
        self.assertNotIn('main', extra['bootmode'])
        self.assertEqual(extra['wifi_modules_loaded'], [])
        self.assertEqual(len(extra['wifi_candidates']), 4)

    def test_measured_fields_from_probes_and_offline_kernel(self):
        measured = self.voyage['measured']
        self.assertEqual(measured['eips_sha256'],
                         '7916bee55c7ec9ab4d2da5859d5b27e3caee77dd971aa93d01fccc8b2fdd6259')
        self.assertEqual(measured['eips_bytes'], 61104)
        self.assertEqual(measured['uname_release'], '3.0.35-lab126')
        self.assertEqual(measured['uname_version'],
                         '#2 PREEMPT Thu Apr 8 09:39:57 UTC 2021')
        self.assertEqual(measured['ram'], [['0x80000000', '0x20000000']])
        self.assertEqual(measured['stock_cmdline'], VOYAGE_CMDLINE)
        self.assertNotEqual(measured['stock_cmdline'], self.pw3['cmdline_base'])
        self.assertIsNone(measured['machine_id'])
        starts = {
            d['name']: d.get('start_512')
            for d in measured['partition_table']['devices']
        }
        self.assertEqual(starts['mmcblk0p1'], 65536)
        self.assertEqual(starts['mmcblk0p2'], 987136)
        self.assertEqual(starts['mmcblk0p3'], 1118208)
        self.assertEqual(starts['mmcblk0p4'], 1249280)
        self.assertIsNone(starts['mmcblk0'])
        self.assertIsNone(starts['mmcblk0boot0'])
        fat = measured['partition_table']['user_fat']
        self.assertEqual(fat['loop_offset_bytes'], 8192)
        self.assertEqual(fat['backing_file'], '/dev/mmcblk0p4')
        funcs = measured['stock_functions']
        for name, digest in STOCK_FUNCTION_SHA256.items():
            self.assertEqual(funcs[name]['sha256'], digest, name)
            self.assertEqual(funcs[name]['bytes'], STOCK_FUNCTION_BYTES[name], name)
            self.assertNotEqual(digest, self.pw3['stock_functions'][name]['sha256'], name)
        self.assertEqual(
            self.voyage['source']['stock_image_sha256'],
            'bb15c17193f8a3b8dba3d27433fd7e6322ac013defcbff5c950ceee703f76530')
        self.assertIs(self.voyage['installable'], False)
        self.assertIs(self.voyage['identity_ready'], False)
        self.assertIs(self.voyage['device_confirmed'], False)

    def test_source_verified_shared_values_are_not_refused(self):
        """4091 and 3.0.35-lab126 are in the Voyage GPL tree, not only on the PW3."""
        ready = json.loads(self.text)
        ready['installable'] = True
        ready['identity_ready'] = True
        ready['device_confirmed'] = True
        ready['device_probe_extra']['bootmode'] = 'main'
        ready['machine'] = self.mod.SOURCE_SHARED_MACHINE_ID
        ready['source']['stock_machine_desc_nr'] = self.mod.SOURCE_SHARED_MACHINE_ID
        ready['measured'] = {
            'eips_sha256': 'a' * 64,
            'eips_bytes': 1,
            'uname_release': self.mod.SOURCE_SHARED_KERNEL_RELEASE,
            'uname_version': '#1 PREEMPT Thu Jan 1 00:00:00 UTC 2015',
            'machine_id': None,
            'stock_cmdline': 'console=ttymxc0,115200 quiet',
            'ram': self.pw3['ram'],
            'partition_table': {'read_from': '/proc/partitions on the device'},
            'stock_functions': {'pm_test_show': {'bytes': 4, 'sha256': 'b' * 64}},
        }
        self.assertEqual(ready['machine'], self.pw3['machine'])
        self.assertEqual(self.mod.problems(ready, self.pw3), [])

    def test_a_complete_reading_that_is_not_the_pw3_record_would_build(self):
        """The gate is fail-closed, not sealed: a real device reading can pass."""
        ready = json.loads(self.text)
        ready['installable'] = True
        ready['identity_ready'] = True
        ready['device_confirmed'] = True
        ready['device_probe_extra']['bootmode'] = 'main'
        ready['machine'] = 4091
        ready['source']['stock_machine_desc_nr'] = 4091
        ready['measured'] = {
            'eips_sha256': 'a' * 64,
            'eips_bytes': 1,
            'uname_release': '3.0.35-lab126',
            'uname_version': '#1 PREEMPT Thu Jan 1 00:00:00 UTC 2015',
            'machine_id': None,
            'stock_cmdline': 'console=ttymxc0,115200',
            'ram': [['0x80000000', '0x20000000']],
            'partition_table': {'read_from': '/proc/partitions on the device'},
            'stock_functions': {'pm_test_show': {'bytes': 1, 'sha256': 'b' * 64}},
        }
        self.assertEqual(self.mod.problems(ready, self.pw3), [])

    def test_filled_voyage_still_blocked_without_flags(self):
        """Evidence can be complete while installable flags stay closed."""
        found = self.mod.problems(self.voyage, self.pw3)
        self.assertIn('installable is not true', found)
        self.assertIn('identity_ready is not true', found)
        self.assertNotIn('measured.stock_cmdline is empty', found)
        self.assertNotIn('measured.stock_functions is empty', found)
        self.assertNotIn('measured.stock_cmdline contains a redacted value', found)
        self.assertNotIn('machine is not the Voyage Wario MACH_TYPE 4091', found)


if __name__ == '__main__':
    unittest.main()
