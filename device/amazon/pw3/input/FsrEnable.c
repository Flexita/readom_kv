/* SPDX-License-Identifier: Apache-2.0
 *
 * Voyage PagePress: stock fsr_keypad probes with event_enable=false and emits
 * no keys until KEYPAD_IOCTL_EVENT_ENABLE. One-shot after modules load.
 * Does not touch pressure/calib/firmware or the touch-active ioctl.
 * Publishes sys.pw3.fsr.enable=ok|errno=N for BootReport (no unique IDs).
 */
#include <cutils/properties.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/ioctl.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <stdint.h>

#ifndef KEYPAD_MAGIC_NUMBER
#define KEYPAD_MAGIC_NUMBER 'B'
#endif
/* Must match include/linux/lab126_keypad.h in the Voyage GPL tree. */
#define KEYPAD_IOCTL_EVENT_ENABLE _IOW(KEYPAD_MAGIC_NUMBER, 0x03, uint32_t)

static void publish(const char *value) {
    /* Best-effort; BootReport reads sys.pw3.fsr.enable. */
    (void)property_set("sys.pw3.fsr.enable", value);
}

int main(void) {
    const char *path = "/dev/keypad";
    int fd = open(path, O_RDWR | O_CLOEXEC);
    if (fd < 0) {
        char buf[64];
        snprintf(buf, sizeof(buf), "open_errno=%d", errno);
        publish(buf);
        fprintf(stderr, "pw3-fsr-enable: open %s: %s\n", path, strerror(errno));
        return 1;
    }
    uint32_t enable = 1;
    int rc;
    do {
        rc = ioctl(fd, KEYPAD_IOCTL_EVENT_ENABLE, &enable);
    } while (rc < 0 && errno == EINTR);
    int err = rc < 0 ? errno : 0;
    close(fd);
    if (err) {
        char buf[64];
        snprintf(buf, sizeof(buf), "errno=%d", err);
        publish(buf);
        fprintf(stderr, "pw3-fsr-enable: EVENT_ENABLE: %s\n", strerror(err));
        return 1;
    }
    publish("ok");
    return 0;
}
