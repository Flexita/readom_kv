# SPDX-License-Identifier: Apache-2.0
"""The image budget has to leave room on a ~3 GB user volume.

The figures are estimates. The system size is the last image that was built
(not rebuilt here). The one-book /data reading and the 3113.9 MiB volume are
Paperwhite 3 measurements kept as a floor, not Voyage readings.
"""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / 'device/amazon/pw3/BoardConfig.mk'
INSTALL_H = ROOT / 'installer/install/install.h'
FLOOR = ROOT / 'device/amazon/pw3/rootdir/pw3-storage-floor.sh'
MIB = 1024 * 1024


def setting(name):
    text = BOARD.read_text()
    found = re.search(r'^%s\s*:=\s*(\d+)\s*$' % name, text, re.M)
    if not found:
        raise AssertionError('no %s in BoardConfig.mk' % name)
    return int(found.group(1))


class StorageBudget(unittest.TestCase):
    def test_sizes_and_format(self):
        system = setting('BOARD_SYSTEMIMAGE_PARTITION_SIZE')
        data = setting('BOARD_USERDATAIMAGE_PARTITION_SIZE')
        fmt = setting('PW3_DATA_FORMAT')
        reserve = 64 * MIB
        self.assertEqual(system, 512 * MIB)
        self.assertEqual(data, 1024 * MIB)
        self.assertEqual(fmt, 2)
        # Above the PW3 one-book /data reading of 748.7 MiB, and not the old
        # 1792 MiB image that asked for ~2.49 GB free.
        self.assertGreater(data, 749 * MIB)
        self.assertLess(data, 1792 * MIB)
        header = INSTALL_H.read_text()
        found = re.search(r'#define INST_RESERVE_BYTES \(64ull << 20\)', header)
        self.assertIsNotNone(found)
        self.assertEqual(reserve, 64 * MIB)
        # install.c: need = max(payload + system, system + data) + reserve
        # when nothing is already on the volume. A payload smaller than the
        # data image is deleted before the data image is written, so the peak
        # is system + data + reserve. A payload larger than data would win.
        payload = 191 * 1000 * 1000
        self.assertLess(payload, data)
        need = max(payload + system, system + data) + reserve
        self.assertEqual(need, 1600 * MIB)
        # A 3 GiB volume with nothing else on it would still keep this much
        # for Kindle books. 3 GiB is the stated total, not a measurement.
        self.assertGreater(3 * 1024 * MIB - need, 1400 * MIB)

    def test_data_image_floor_is_explicit(self):
        text = FLOOR.read_text()
        self.assertIn('sys_storage_threshold_percentage 20', text)
        self.assertIn('sys_storage_threshold_max_bytes 134217728', text)
        data = setting('BOARD_USERDATAIMAGE_PARTITION_SIZE')
        floor = 134217728
        self.assertLess(floor, data // 2)
        self.assertGreater(floor, 64 * MIB)
        probe = ROOT / 'tools/voyage-readonly-probe.sh'
        subprocess.run(['sh', str(probe), '--self-test'], check=True)


if __name__ == '__main__':
    unittest.main()
