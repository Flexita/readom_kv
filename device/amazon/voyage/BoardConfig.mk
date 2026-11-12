# SPDX-License-Identifier: Apache-2.0
# Same image budget as the shared board config (512 MiB system, 1024 MiB
# data, format 2). No handoff addresses are set here.
include device/amazon/pw3/BoardConfig.mk

TARGET_BOOTLOADER_BOARD_NAME := voyage
