#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Read-only Voyage stock probes for original_boot() pins (hashes + sizes only).
# Run on the jailbroken Voyage as root. Does not print board_id, MAC, serial,
# or any other unique identifier. Does not upload. Does not write outside the
# path you pass (default: current directory report file).
#
# Necessity: helper.c profile-3 original_boot() currently returns 1 because
# /sbin/init, /etc/upstart/init.sh, and /sbin/init.exe body hashes are not in
# measured.*. Stock identity still runs via eips + uname + dd_device_matches;
# this probe only fills the optional init-body pin Paperwhite already has.
set -eu
umask 077
OUT=${1:-./voyage-original-boot-probe.txt}
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

{
  echo "schema=voyage-original-boot-probe-v1"
  echo "privacy=hashes_and_sizes_only"
  echo "note=no_board_id_mac_serial"
  for path in /sbin/init /etc/upstart/init.sh /sbin/init.exe; do
    if [ -f "$path" ] && [ ! -L "$path" ]; then
      bytes=$(wc -c < "$path" | tr -d ' ')
      digest=$(sha256sum "$path" | cut -d ' ' -f 1)
      echo "path=$path"
      echo "bytes=$bytes"
      echo "sha256=$digest"
    else
      echo "path=$path"
      echo "missing_or_symlink=1"
    fi
  done
  # Root mount options only (ro/rw) — not a unique id.
  awk '$2=="/" { print "root_mount_options="$4; exit }' /proc/mounts
} > "$TMP"

# Strip any accidental unique tokens if a future edit adds them.
if grep -Ei 'board_id|serial|mac|wlan0|eth0|address' "$TMP" >/dev/null 2>&1; then
  echo "refusing to write: probe output looked like it contained a unique id" >&2
  exit 2
fi
cp "$TMP" "$OUT"
echo "wrote $OUT (hashes/sizes only; keep local — do not commit unique-bearing logs)"
