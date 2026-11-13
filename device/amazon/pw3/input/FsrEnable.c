/* SPDX-License-Identifier: Apache-2.0
 *
 * Voyage PagePress: stock fsr_keypad probes with event_enable=false and emits
 * no keys until KEYPAD_IOCTL_EVENT_ENABLE. One-shot after modules load.
 * Does not touch pressure/calib/firmware or the touch-active ioctl.
 */
#include <errno.h>
#include <fcntl.h>
#include <linux/ioctl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#ifndef KEYPAD_MAGIC_NUMBER
#define KEYPAD_MAGIC_NUMBER 'B'
#endif
/* Must match include/linux/lab126_keypad.h in the Voyage GPL tree. */
#define KEYPAD_IOCTL_EVENT_ENABLE _IOW(KEYPAD_MAGIC_NUMBER, 0x03, uint32_t)

int main(void) {
    const char *path = "/dev/keypad";
    int fd = open(path, O_RDWR | O_CLOEXEC);
    if (fd < 0) {
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
        fprintf(stderr, "pw3-fsr-enable: EVENT_ENABLE: %s\n", strerror(err));
        return 1;
    }
    return 0;
}
