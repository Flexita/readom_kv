#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Read-only notes for a Voyage port. Prints to stdout. Does not mount, write,
# download, or sign in. Drops serial numbers, MAC-shaped strings and 12-digit
# hex ids before anything is printed. Run it on the Kindle only when you mean
# to; this repository does not run it against a device.
#
#   sh voyage-readonly-probe.sh
#   sh voyage-readonly-probe.sh --self-test
set -eu

redact() {
    sed -E \
        -e '/^[Ss]erial[[:space:]]*:/d' \
        -e '/[Bb]oard[[:space:]]*[Ii][Dd]/d' \
        -e '/[Mm][Aa][Cc][[:space:]]*[Aa]ddress/d' \
        -e 's/([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}/[mac]/g' \
        -e 's/\b[0-9A-Fa-f]{12}\b/[id]/g'
}

collect() {
    echo '## uname'
    uname -a 2>/dev/null || echo 'uname failed'
    echo '## version'
    sed -n '1,5p' /proc/version 2>/dev/null || echo 'no /proc/version'
    echo '## cpuinfo'
    grep -E 'Hardware|Revision|Processor|model name|CPU' /proc/cpuinfo 2>/dev/null || true
    echo '## eips'
    if [ -f /usr/sbin/eips ]; then
        wc -c /usr/sbin/eips
        sha256sum /usr/sbin/eips 2>/dev/null || sha256 /usr/sbin/eips 2>/dev/null || echo 'no sha256'
    else
        echo 'no /usr/sbin/eips'
    fi
    echo '## cmdline'
    tr '\0' '\n' < /proc/cmdline 2>/dev/null || echo 'no cmdline'
    echo '## iomem'
    awk '$1=="System" || /System RAM/ {print}' /proc/iomem 2>/dev/null || true
    echo '## partitions'
    awk '$4 ~ /mmcblk0/ {print}' /proc/partitions 2>/dev/null || true
    echo '## blocks'
    if [ -r /sys/class/block/mmcblk0/size ]; then
        echo "mmcblk0 size $(cat /sys/class/block/mmcblk0/size)"
    fi
    for b in mmcblk0 mmcblk0p1 mmcblk0p2 mmcblk0p3 mmcblk0p4 mmcblk0boot0 mmcblk0boot1; do
        ro='?'
        sz='?'
        if [ -r "/sys/class/block/$b/ro" ]; then ro=$(cat "/sys/class/block/$b/ro"); fi
        if [ -r "/sys/class/block/$b/size" ]; then sz=$(cat "/sys/class/block/$b/size"); fi
        if [ "$ro" != '?' ] || [ "$sz" != '?' ]; then
            echo "$b ro=$ro size=$sz"
        fi
    done
    echo '## df'
    df -k /mnt/us /mnt/base-us 2>/dev/null || df -k 2>/dev/null | awk 'NR==1 || /\/mnt\//' || true
}

self_test() {
    # Built at run time so this file does not contain a MAC or a Kindle serial.
    mac=$(printf '%s:%s:%s:%s:%s:%s' aa bb cc dd ee ff)
    serial=$(printf '%s%s' 'G0' '00123456789012')
    sample="Serial          : ${serial}
Hardware        : Amazon MX6SL Wario Board
Revision        : 0005
MAC Address     : ${mac}
board id ${serial}
cmdline console=ttymxc0,115200
eips 73eb0d2532f9c899e98fb8feacb7a085ab0652f628f1c2c7b2e2d1cefae3f4ae
"
    out=$(printf '%s\n' "$sample" | redact)
    printf '%s\n' "$out" | grep -q 'Hardware' || { echo 'self-test: hardware line dropped'; return 1; }
    printf '%s\n' "$out" | grep -q '73eb0d2532f9c899e98fb8feacb7a085ab0652f628f1c2c7b2e2d1cefae3f4ae' || {
        echo 'self-test: long hash was damaged'; return 1; }
    printf '%s\n' "$out" | grep -q 'Serial' && { echo 'self-test: serial line survived'; return 1; }
    printf '%s\n' "$out" | grep -F -q "$mac" && { echo 'self-test: mac survived'; return 1; }
    printf '%s\n' "$out" | grep -F -q "$serial" && { echo 'self-test: serial survived'; return 1; }
    true
    echo 'self-test ok'
}

if [ "${1:-}" = '--self-test' ]; then
    self_test
    exit 0
fi

collect | redact
