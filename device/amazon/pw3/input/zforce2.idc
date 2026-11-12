# Voyage Neonode zforce2 (input name ZF_INPUT_NAME "zforce2").
# Without touch.deviceType=touchScreen, AOSP InputReader defaults this ABS_MT
# device to DEVICE_TYPE_POINTER → AINPUT_SOURCE_MOUSE (invisible cursor), so
# taps never become touchscreen MotionEvents. Packed ea509373… lacked this file.
device.internal = 1
touch.deviceType = touchScreen
touch.orientationAware = 1
