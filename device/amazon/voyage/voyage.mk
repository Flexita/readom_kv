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

# Voyage ALS auto-brightness overlay (requires als_max44009 + sensors.pw3).
DEVICE_PACKAGE_OVERLAYS += $(LOCAL_PATH)/overlay

# PagePress EVENT_ENABLE oneshot + ALS TYPE_LIGHT HAL (HIDL wraps sensors.pw3).
PRODUCT_PACKAGES += \
    pw3-fsr-enable \
    sensors.pw3 \
    android.hardware.sensors@1.0-impl \
    android.hardware.sensors@1.0-service

PRODUCT_COPY_FILES += \
    frameworks/native/data/etc/android.hardware.sensor.light.xml:system/etc/permissions/android.hardware.sensor.light.xml \
    device/amazon/pw3/input/fsr_keypad.kl:system/usr/keylayout/fsr_keypad.kl

PRODUCT_PROPERTY_OVERRIDES += \
    ro.hardware.sensors=pw3
