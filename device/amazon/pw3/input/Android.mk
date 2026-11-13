LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := pw3-fsr-enable
LOCAL_SRC_FILES := FsrEnable.c
LOCAL_CFLAGS := -Wall -Wextra -Werror
LOCAL_INIT_RC := pw3-fsr-enable.rc
include $(BUILD_EXECUTABLE)
