#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Minimal read-only capture around a handoff module_load failure on Voyage.
# Run as root on stock firmware AFTER a failed tap that logged
#   PW3_FIRST_KERNEL_CHECK_FAIL check=module_load errno=…
# Does not load modules, does not touch /dev/mem /proc/kcore / boot partitions,
# does not print board_id / MAC / serial. Keep the report local — do not upload
# or commit unique-bearing logs.
#
# Necessity: userspace only sees errno from init_module. The stock kernel's
# reject reason (vermagic / reloc / symbol / init return) is in the ring buffer.
set -eu
umask 077
OUT=${1:-./voyage-module-load-probe.txt}
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

{
  echo "schema=voyage-module-load-probe-v1"
  echo "privacy=filtered_dmesg_and_uname_only"
  echo "note=no_board_id_mac_serial_no_mem_no_kcore"
  # Stock identity pins only (already public in the profile).
  echo "uname_release=$(uname -r)"
  echo "uname_version=$(uname -v)"
  echo "uname_machine=$(uname -m)"
  # Ring buffer: keep lines that name modules / vermagic / init_module / our ko.
  # Drop anything that looks like a unique hardware id.
  if command -v dmesg >/dev/null 2>&1; then
    dmesg 2>/dev/null | grep -Ei 'vermagic|disagrees about version|Invalid module format|Unknown symbol|pw3_first_kernel|init_module|module_load|reloc' \
      | grep -Eiv 'board_id|serial|mac|wlan0|eth0|address|([0-9a-f]{2}:){5}[0-9a-f]{2}' \
      | tail -n 40 \
      | sed 's/^/dmesg=/'
  else
    echo "dmesg_missing=1"
  fi
  # Confirm MODVERSIONS is not something we can read from userspace reliably;
  # /proc/config.gz may be absent on stock. Record presence only.
  if [ -f /proc/config.gz ]; then
    if gzip -dc /proc/config.gz 2>/dev/null | grep -q '^CONFIG_MODVERSIONS=y'; then
      echo "proc_config_modversions=y"
    else
      echo "proc_config_modversions=n_or_unset"
    fi
  else
    echo "proc_config_gz=absent"
  fi
} > "$TMP"

if grep -Ei 'board_id|serial|=mac|wlan0|eth0|address|([0-9a-f]{2}:){5}[0-9a-f]{2}' "$TMP" >/dev/null 2>&1; then
  echo "refusing to write: probe output looked like it contained a unique id" >&2
  exit 2
fi
cp "$TMP" "$OUT"
echo "wrote $OUT (filtered; keep local)"
