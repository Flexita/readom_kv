# SPDX-License-Identifier: Apache-2.0
# Voyage product name on top of the i.MX6SL board code. "pw3" in the inherited
# makefile is the platform name this tree already uses (init scripts, HALs),
# not a claim that this image has booted on a Voyage. Heap settings are left
# as they were measured on that platform; changing them here without a new
# measurement would not be an optimization.
$(call inherit-product, device/amazon/pw3/pw3.mk)

PRODUCT_NAME := voyage
PRODUCT_DEVICE := voyage
PRODUCT_BRAND := Readom
PRODUCT_MODEL := Kindle Voyage
PRODUCT_MANUFACTURER := Readom
