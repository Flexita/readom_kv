# SPDX-License-Identifier: Apache-2.0
# Same image budget as the shared board config (512 MiB system, 1024 MiB
# data, format 2). No handoff addresses are set here.
include device/amazon/pw3/BoardConfig.mk

# Override pw3's WITH_DEXPREOPT := true. Native amd64 host dex2oatd cannot
# MAP_FIXED the ARM boot.art at 0x7039b000 (Failed to mmap … instead of that
# address), so app package.odex rules abort systemimage. Command-line
# WITH_DEXPREOPT=false does not beat BoardConfig := true under kati here.
# Disabling host preopt lets an experimental voyage-userdebug image finish;
# on-device compile stays unverified and does not authorize install or boot.
WITH_DEXPREOPT := false

TARGET_BOOTLOADER_BOARD_NAME := voyage
