#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Floor for the 1024 MiB data image. AOSP 8.1 StorageManager.getStorageLowBytes
# (android-8.1.0_r81, core/java/android/os/storage/StorageManager.java) is
# min(percent% of the volume, max bytes). The Java defaults are 5 and 500 MiB,
# so on a 1024 MiB volume the cap never binds and "low" is about 50 MiB.
# 20% of 1024 MiB is about 205 MiB; the cap below pulls the floor to 128 MiB.
# DeviceStorageMonitorService trims cache as free space nears that floor.
# Either value can be changed after boot:
#   settings put global sys_storage_threshold_percentage <1-100>
#   settings put global sys_storage_threshold_max_bytes <bytes>
# This file is not in an image until that image is built from this tree.
settings put global sys_storage_threshold_percentage 20
settings put global sys_storage_threshold_max_bytes 134217728
