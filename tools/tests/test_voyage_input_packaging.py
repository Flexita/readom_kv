#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Static Voyage input packaging vs EventHub/InputReader contracts.

Does not claim device hardware behavior. After the idc rebuild, packed
system.raw under voyage-experimental-PRIVATE-candidate-zforce-idc-* must
contain zforce2.idc (touchScreen) while retaining cyttsp4_mt.idc. Source and
pw3.mk must still ship the copy rule. FSR/ABS caveats remain separate.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IDC_SRC = ROOT / 'device/amazon/pw3/input/zforce2.idc'
CYT_SRC = ROOT / 'device/amazon/pw3/input/cyttsp4_mt.idc'
PW3_MK = ROOT / 'device/amazon/pw3/pw3.mk'
VOYAGE_HW = ROOT / 'tools/kernel-hardware/init.voyage.hardware.rc'
ZF_HDR = Path('/home/builder/pw3-build/linux-android-core/include/linux/zforce2.h')
ZF_NAME = Path('/home/builder/pw3-build/linux-android-core/drivers/input/touchscreen/zforceint2.h')
FSR_C = Path('/home/builder/pw3-build/linux-android-core/drivers/input/keyboard/fsr_keypad.c')
INPUT_READER = Path(
    '/home/builder/android-src/frameworks/native/services/inputflinger/InputReader.cpp')
PACKED_RAW = Path(
    '/mnt/build-share/voyage-experimental-PRIVATE-candidate-zforce-idc-20261112/export/system.raw.img')
# Prior defect image (kept for regression contrast; not required on host).
PACKED_RAW_PRE_IDC = Path(
    '/mnt/build-share/voyage-experimental-PRIVATE-candidate-zforce-20261112/export/system.raw.img')


class VoyageInputPackaging(unittest.TestCase):
    def test_source_ships_zforce2_idc_as_touchscreen(self):
        self.assertTrue(IDC_SRC.is_file())
        text = IDC_SRC.read_text()
        self.assertIn('touch.deviceType = touchScreen', text)
        self.assertIn('device.internal = 1', text)
        mk = PW3_MK.read_text()
        self.assertIn('input/zforce2.idc:system/usr/idc/zforce2.idc', mk)
        # Keep PW3 cyttsp idc for dual naming; Voyage loads zforce2 only.
        self.assertTrue(CYT_SRC.is_file())
        self.assertIn('cyttsp4_mt.idc', mk)

    def test_voyage_hw_loads_zforce_fsr_haptics(self):
        text = VOYAGE_HW.read_text()
        self.assertIn('insmod /vendor/lib/modules/zforce2.ko', text)
        self.assertIn('insmod /vendor/lib/modules/fsr_keypad.ko', text)
        self.assertIn('insmod /vendor/lib/modules/drv26xx_haptics.ko', text)
        self.assertNotIn('insmod /vendor/lib/modules/cyttsp', text)

    def test_kernel_input_name_is_zforce2_not_cyttsp(self):
        if not ZF_NAME.is_file():
            self.skipTest('android-core tree not on host')
        self.assertIn('#define ZF_INPUT_NAME               "zforce2"', ZF_NAME.read_text())

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

    def test_fsr_event_enable_is_set_only_ioctl_no_get(self):
        """Stock Lab126 contract: enable is write-only; BootReport cannot sample it."""
        hdr = Path('/home/builder/pw3-build/linux-android-core/include/linux/lab126_keypad.h')
        if not hdr.is_file():
            self.skipTest('lab126_keypad.h not on host')
        text = hdr.read_text()
        self.assertIn('KEYPAD_IOCTL_EVENT_ENABLE', text)
        self.assertIn('KEYPAD_IOCTL_TOUCH_ACTIVE', text)
        self.assertIn('PATH_DEV_KEYPAD', text)
        self.assertNotIn('EVENT_ENABLE_GET', text)
        self.assertNotIn('GET_EVENT_ENABLE', text)

    def test_zforce_dbglog_defaults_off(self):
        """Without dbglog=1, I/E zforce: lines never hit the ring — silence ≠ failure."""
        src = Path('/home/builder/pw3-build/linux-android-core/drivers/input/touchscreen/zforce2.c')
        if not src.is_file():
            self.skipTest('zforce2.c not on host')
        text = src.read_text()
        self.assertIn('static uint dbglog = 0;', text)
        self.assertIn('module_param_named(dbglog, dbglog, uint, S_IRUGO);', text)

    def test_stock_and_android_core_zforce_fsr_sources_match(self):
        """Official reuse: Voyage android-core drivers are the Lab126 GPL sources."""
        pairs = [
            ('drivers/input/touchscreen/zforce2.c', 'drivers/input/touchscreen/zforce2.c'),
            ('drivers/input/keyboard/fsr_keypad.c', 'drivers/input/keyboard/fsr_keypad.c'),
            ('include/linux/zforce2.h', 'include/linux/zforce2.h'),
        ]
        stock = Path('/home/builder/pw3-build/linux-stock')
        android = Path('/home/builder/pw3-build/linux-android-core')
        if not (stock / pairs[0][0]).is_file() or not (android / pairs[0][0]).is_file():
            self.skipTest('stock/android-core trees not on host')
        for rel, _ in pairs:
            self.assertEqual(
                (stock / rel).read_bytes(),
                (android / rel).read_bytes(),
                msg=f'{rel} diverges stock vs android-core')

    def test_stock_ko_vermagic_differs_from_android81(self):
        """Cannot copy stock .ko into Voyage Android: vermagic / ABI differ."""
        import subprocess
        stock_ko = Path('/home/builder/pw3-build/out-stock-voyage/drivers/input/touchscreen/zforce2.ko')
        and_ko = Path(
            '/tmp/voyage-mod-compare/lib/modules/3.0.35-lab126-voyage-android81'
            '/kernel/drivers/input/touchscreen/zforce2.ko')
        if not stock_ko.is_file():
            self.skipTest('stock zforce2.ko not on host')
        if not and_ko.is_file():
            # Extract once from the private modules tar when present.
            tar = Path('/mnt/build-share/android-core-kernel-voyage/modules.tar.gz')
            if not tar.is_file():
                self.skipTest('android81 zforce2.ko not on host')
            and_ko.parent.mkdir(parents=True, exist_ok=True)
            subprocess.check_call(
                ['tar', '-xzf', str(tar), '-C', '/tmp/voyage-mod-compare',
                 'lib/modules/3.0.35-lab126-voyage-android81/kernel/drivers/input/touchscreen/zforce2.ko'])
        stock_v = subprocess.check_output(['modinfo', '-F', 'vermagic', str(stock_ko)], text=True).strip()
        and_v = subprocess.check_output(['modinfo', '-F', 'vermagic', str(and_ko)], text=True).strip()
        self.assertIn('3.0.35-lab126', stock_v)
        self.assertIn('voyage-android81', and_v)
        self.assertNotEqual(stock_v, and_v)

    def test_fsr_fw_header_is_empty_stub(self):
        """GPL tree does not ship KL05 app firmware; normal boot uses on-MCU ROM."""
        fw = Path('/home/builder/pw3-build/linux-android-core/drivers/input/keyboard/fsr_fw.h')
        if not fw.is_file():
            self.skipTest('fsr_fw.h not on host')
        text = fw.read_text()
        self.assertIn('u8 fsr_fw_img[] = {};', text)
        self.assertIn('fw_lines = 0', text)

    def test_userlog_allow_omits_zforce_and_fsr_prefixes(self):
        """Courtesy previous-kernel cannot show digitizer init under today's filter."""
        userlog = ROOT / 'boot/launcher/userlog.c'
        text = userlog.read_text()
        start = text.index('static const char *const ALLOW[]')
        end = text.index('};', start)
        allow = text[start:end]
        for forbidden in ('zforce', 'fsr:', 'fsr_keypad', 'I zforce', 'E zforce'):
            self.assertNotIn(f'"{forbidden}', allow)
            self.assertNotIn(f'"{forbidden}"', allow)

    def test_zforce_header_resolution_is_not_voyage_panel(self):
        # Static mismatch to document: packed ko uses 600x800; Voyage panel 1448x1072.
        if not ZF_HDR.is_file():
            self.skipTest('zforce2.h not on host')
        text = ZF_HDR.read_text()
        self.assertIn('#define X_RESOLUTION                600', text)
        self.assertIn('#define Y_RESOLUTION                800', text)

    def test_packed_idc_rebuild_ships_zforce2_touchscreen_idc(self):
        if not PACKED_RAW.is_file():
            self.skipTest('packed idc system.raw not on host')
        import subprocess
        out = subprocess.check_output(
            ['debugfs', '-R', 'ls -l /usr/idc', str(PACKED_RAW)],
            text=True, stderr=subprocess.STDOUT)
        self.assertIn('cyttsp4_mt.idc', out)
        self.assertIn('zforce2.idc', out)
        body = subprocess.check_output(
            ['debugfs', '-R', 'cat /usr/idc/zforce2.idc', str(PACKED_RAW)],
            text=True, stderr=subprocess.STDOUT)
        self.assertIn('touch.deviceType = touchScreen', body)
        self.assertIn('device.internal = 1', body)

    def test_pre_idc_ea509373_image_lacked_zforce2_idc(self):
        if not PACKED_RAW_PRE_IDC.is_file():
            self.skipTest('pre-idc packed system.raw not on host')
        import subprocess
        out = subprocess.check_output(
            ['debugfs', '-R', 'ls -l /usr/idc', str(PACKED_RAW_PRE_IDC)],
            text=True, stderr=subprocess.STDOUT)
        self.assertIn('cyttsp4_mt.idc', out)
        self.assertNotIn('zforce2.idc', out)


if __name__ == '__main__':
    unittest.main()
