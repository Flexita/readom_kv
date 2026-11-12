# SPDX-License-Identifier: Apache-2.0
"""The image budget has to leave room on a ~3 GB user volume.

The figures are estimates. The system size is the last image that was built
(not rebuilt here). The one-book /data reading and the 3113.9 MiB volume are
Paperwhite 3 measurements kept as a floor, not Voyage readings.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / 'device/amazon/pw3/BoardConfig.mk'
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
        need = system + data + reserve
        self.assertEqual(need, 1600 * MIB)
        # A 3 GiB volume with nothing else on it would still keep this much
        # for Kindle books. 3 GiB is the stated total, not a measurement.
        self.assertGreater(3 * 1024 * MIB - need, 1400 * MIB)


if __name__ == '__main__':
    unittest.main()
