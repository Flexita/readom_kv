/* SPDX-License-Identifier: Apache-2.0
 *
 * Voyage ALS (MAX44009) → Sensor.TYPE_LIGHT via /dev/als ALS_IOCTL_GET_LUX.
 * Returns zero sensors when /dev/als is absent (PW3 / modules not loaded).
 * Does not invent lux, write calibration, or enable chip auto-mode ioctl.
 */
#include <hardware/sensors.h>
#include <log/log.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/ioctl.h>
#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

#ifndef ALS_MAGIC_NUMBER
#define ALS_MAGIC_NUMBER 'A'
#endif
#define ALS_IOCTL_GET_LUX _IOR(ALS_MAGIC_NUMBER, 0x01, int)

#define HANDLE_LIGHT 1
#define MIN_DELAY_US 200000   /* 5 Hz ceiling — e-ink friendly */
#define MAX_DELAY_US 2000000  /* 0.5 Hz floor */

struct pw3_sensors {
    struct sensors_poll_device_1 device;
    int als_fd;
    int enabled;
    int64_t period_ns;
    int64_t last_event_ns;
    float last_lux;
    int have_last;
    int pending_flush;
    pthread_mutex_t lock;
};

static int64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_BOOTTIME, &ts);
    return (int64_t)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

static int als_present(void) {
    int fd = open("/dev/als", O_RDONLY | O_CLOEXEC);
    if (fd < 0) return 0;
    close(fd);
    return 1;
}

static int read_lux(int fd, float *out) {
    int lux = 0;
    int rc;
    do {
        rc = ioctl(fd, ALS_IOCTL_GET_LUX, &lux);
    } while (rc < 0 && errno == EINTR);
    if (rc < 0) return -errno;
    if (lux < 0) lux = 0;
    *out = (float)lux;
    return 0;
}

static struct sensor_t g_light = {
    .name = "MAX44009 Ambient Light",
    .vendor = "Maxim/Lab126",
    .version = 1,
    .handle = HANDLE_LIGHT,
    .type = SENSOR_TYPE_LIGHT,
    .maxRange = 188000.0f,
    .resolution = 1.0f,
    .power = 0.09f,
    .minDelay = MIN_DELAY_US,
    .fifoReservedEventCount = 0,
    .fifoMaxEventCount = 0,
    .stringType = SENSOR_STRING_TYPE_LIGHT,
    .requiredPermission = "",
    .maxDelay = MAX_DELAY_US,
    .flags = SENSOR_FLAG_ON_CHANGE_MODE,
};

static int get_sensors_list(struct sensors_module_t *module,
                            struct sensor_t const **list) {
    (void)module;
    if (!als_present()) {
        *list = NULL;
        return 0;
    }
    *list = &g_light;
    return 1;
}

static int set_operation_mode(unsigned int mode) {
    return mode == 0 ? 0 : -EINVAL;
}

static int activate(struct sensors_poll_device_t *dev, int handle, int enabled) {
    struct pw3_sensors *s = (struct pw3_sensors *)dev;
    if (handle != HANDLE_LIGHT) return -EINVAL;
    pthread_mutex_lock(&s->lock);
    if (enabled) {
        if (s->als_fd < 0) {
            s->als_fd = open("/dev/als", O_RDONLY | O_CLOEXEC);
            if (s->als_fd < 0) {
                int err = -errno;
                pthread_mutex_unlock(&s->lock);
                return err;
            }
        }
        s->enabled = 1;
        s->have_last = 0;
        s->last_event_ns = 0;
    } else {
        s->enabled = 0;
        s->have_last = 0;
        if (s->als_fd >= 0) {
            close(s->als_fd);
            s->als_fd = -1;
        }
    }
    pthread_mutex_unlock(&s->lock);
    return 0;
}

static int set_delay(struct sensors_poll_device_t *dev, int handle, int64_t ns) {
    struct pw3_sensors *s = (struct pw3_sensors *)dev;
    if (handle != HANDLE_LIGHT) return -EINVAL;
    if (ns < (int64_t)MIN_DELAY_US * 1000LL) ns = (int64_t)MIN_DELAY_US * 1000LL;
    if (ns > (int64_t)MAX_DELAY_US * 1000LL) ns = (int64_t)MAX_DELAY_US * 1000LL;
    pthread_mutex_lock(&s->lock);
    s->period_ns = ns;
    pthread_mutex_unlock(&s->lock);
    return 0;
}

static int batch(struct sensors_poll_device_1 *dev, int handle, int flags,
                 int64_t period_ns, int64_t max_latency_ns) {
    (void)flags;
    (void)max_latency_ns;
    return set_delay(&dev->v0, handle, period_ns);
}

static int flush_sensor(struct sensors_poll_device_1 *dev, int handle) {
    struct pw3_sensors *s = (struct pw3_sensors *)dev;
    if (handle != HANDLE_LIGHT) return -EINVAL;
    pthread_mutex_lock(&s->lock);
    if (!s->enabled) {
        pthread_mutex_unlock(&s->lock);
        return -EINVAL;
    }
    s->pending_flush = 1;
    pthread_mutex_unlock(&s->lock);
    return 0;
}

static int poll_events(struct sensors_poll_device_t *dev,
                       sensors_event_t *data, int count) {
    struct pw3_sensors *s = (struct pw3_sensors *)dev;
    if (count < 1) return -EINVAL;

    for (;;) {
        pthread_mutex_lock(&s->lock);
        if (s->pending_flush) {
            s->pending_flush = 0;
            memset(&data[0], 0, sizeof(data[0]));
            data[0].version = META_DATA_VERSION;
            data[0].sensor = -1;
            data[0].type = SENSOR_TYPE_META_DATA;
            data[0].timestamp = now_ns();
            data[0].meta_data.what = META_DATA_FLUSH_COMPLETE;
            data[0].meta_data.sensor = HANDLE_LIGHT;
            pthread_mutex_unlock(&s->lock);
            return 1;
        }
        if (!s->enabled || s->als_fd < 0) {
            pthread_mutex_unlock(&s->lock);
            usleep(50000);
            continue;
        }
        int64_t period = s->period_ns;
        int64_t last = s->last_event_ns;
        int fd = s->als_fd;
        float prev = s->last_lux;
        int have = s->have_last;
        pthread_mutex_unlock(&s->lock);

        int64_t t = now_ns();
        int64_t wait_ns = period - (t - last);
        if (last > 0 && wait_ns > 1000000LL) {
            usleep((useconds_t)(wait_ns / 1000LL));
            continue;
        }

        float lux = 0;
        if (read_lux(fd, &lux) != 0) {
            usleep(100000);
            continue;
        }

        /* On-change: first sample always; later only if lux moved. */
        if (have && lux == prev) {
            pthread_mutex_lock(&s->lock);
            s->last_event_ns = now_ns();
            pthread_mutex_unlock(&s->lock);
            usleep((useconds_t)(period / 1000LL));
            continue;
        }

        memset(&data[0], 0, sizeof(data[0]));
        data[0].version = sizeof(sensors_event_t);
        data[0].sensor = HANDLE_LIGHT;
        data[0].type = SENSOR_TYPE_LIGHT;
        data[0].timestamp = now_ns();
        data[0].light = lux;

        pthread_mutex_lock(&s->lock);
        s->last_lux = lux;
        s->have_last = 1;
        s->last_event_ns = data[0].timestamp;
        pthread_mutex_unlock(&s->lock);
        return 1;
    }
}

static int close_device(struct hw_device_t *dev) {
    struct pw3_sensors *s = (struct pw3_sensors *)dev;
    if (!s) return 0;
    pthread_mutex_lock(&s->lock);
    if (s->als_fd >= 0) close(s->als_fd);
    s->als_fd = -1;
    pthread_mutex_unlock(&s->lock);
    pthread_mutex_destroy(&s->lock);
    free(s);
    return 0;
}

static int open_sensors(const struct hw_module_t *module, const char *id,
                        struct hw_device_t **device) {
    if (!device || !id || strcmp(id, SENSORS_HARDWARE_POLL)) return -EINVAL;
    struct pw3_sensors *s = calloc(1, sizeof(*s));
    if (!s) return -ENOMEM;
    s->als_fd = -1;
    s->period_ns = (int64_t)MIN_DELAY_US * 1000LL;
    pthread_mutex_init(&s->lock, NULL);
    s->device.common.tag = HARDWARE_DEVICE_TAG;
    s->device.common.version = SENSORS_DEVICE_API_VERSION_1_3;
    s->device.common.module = (struct hw_module_t *)module;
    s->device.common.close = close_device;
    s->device.activate = activate;
    s->device.setDelay = set_delay;
    s->device.poll = poll_events;
    s->device.batch = batch;
    s->device.flush = flush_sensor;
    *device = &s->device.common;
    return 0;
}

static struct hw_module_methods_t g_methods = {
    .open = open_sensors,
};

struct sensors_module_t HAL_MODULE_INFO_SYM = {
    .common = {
        .tag = HARDWARE_MODULE_TAG,
        .version_major = 1,
        .version_minor = 3,
        .id = SENSORS_HARDWARE_MODULE_ID,
        .name = "PW3/Voyage ALS sensors",
        .author = "Readom",
        .methods = &g_methods,
    },
    .get_sensors_list = get_sensors_list,
    .set_operation_mode = set_operation_mode,
};
