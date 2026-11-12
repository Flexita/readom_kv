#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Minimal Voyage read-only probe: /proc/bootmode only.
#
# Why this exists: dd_atags refuses to build the handoff ATAG list unless
# bootmode is exactly "main". The extra probe saw an empty string. That empty
# reading must not be rewritten as main. This script asks again for that one
# field and nothing else.
#
# Safe scope: only /proc/bootmode. Does not open memory devices, boot block
# nodes, identity proc nodes, load drivers, or start the Android entry.
# Run as root on the device, e.g. copy to /mnt/us/RUNME.sh and type ;log runme.
# Writes only /mnt/us/voyage-probe-bootmode.txt.

set -eu

OUT="${VOYAGE_PROBE_OUT:-/mnt/us/voyage-probe-bootmode.txt}"
ROOT="${VOYAGE_PROBE_ROOT:-}"

note_error() {
	errors=$((errors + 1))
	echo "error: $1"
}

errors=0

{
	echo "VOYAGE_READONLY_PROBE_BOOTMODE"
	echo "generated: $(date -u 2>/dev/null || date)"
	echo
	echo "== id =="
	id
	echo
	echo "== bootmode =="
	bm="$ROOT/proc/bootmode"
	if [ ! -r "$bm" ]; then
		note_error "cannot read bootmode"
		echo "bootmode: unreadable"
	else
		# Single line, strip CR; do not invent a value.
		mode=$(tr -d '\r' < "$bm" | sed -n '1p')
		case "$mode" in
			main|diags)
				echo "bootmode: $mode"
				;;
			"")
				note_error "bootmode empty"
				echo "bootmode: withheld (empty)"
				;;
			*)
				echo "bootmode: withheld (not main or diags)"
				echo "bootmode_len: ${#mode}"
				;;
		esac
	fi
	echo
	echo "== note =="
	echo "MACH_TYPE is not read here. It is a build pin proven offline."
	echo "This script does not read identity proc nodes or memory devices."
	echo
	echo "== result =="
	if [ "$errors" -eq 0 ]; then
		echo "result: ok"
	else
		echo "result: partial"
	fi
	echo "errors: $errors"
	echo "VOYAGE_PROBE_BOOTMODE_DONE"
} > "$OUT"

# Best-effort on-screen hint when eips exists (Kindle).
if [ -x /usr/sbin/eips ]; then
	/usr/sbin/eips 1 1 "bootmode probe done" 2>/dev/null || true
	/usr/sbin/eips 1 2 "see voyage-probe-bootmode.txt" 2>/dev/null || true
fi

exit 0
