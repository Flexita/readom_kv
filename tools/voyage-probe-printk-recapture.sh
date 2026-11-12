#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Minimal READ-ONLY recapture of /proc/printkbuf after a Voyage handoff reboot.
#
# Place as /mnt/us/RUNME.sh, eject USB data, then on the Kindle search box:
#   ;log runme
# Writes ONLY:
#   /mnt/us/voyage-printk-recapture.txt
# Screen (eips): "printk capture" + complete|partial|write failed|absent
#
# Does NOT: run the installer/launcher, reboot, mount/remount, insmod,
# rewrite android/state or planted report.bin, read /dev/mem /proc/kcore,
# touch boot partitions, or write the raw ring to disk.
#
# Why this exists (190630 + 183552):
#   Launcher previous-kernel.txt kept STOPPED but dropped the stop *reason*
#   "testfile configuration or complete command line rejected" because
#   boot/launcher/userlog.c identifier() treats the substring "command line"
#   as a unique-id word. Expanding ALLOW patterns alone cannot recover it —
#   the line already matches "pw3-" and is dropped at the second gate.
#   This script keeps that fixed PreInit sentence (and other pw3-preinit /
#   pw3-handoff fixed text) while still refusing MAC/serial/board_id/ssid
#   and long hex runs. Raw ring is never written.
#
# Busybox / POSIX: ash-compatible. Uses: cat, dd, wc, grep, sed, awk, tr,
# printf, cp, rm, mkdir, date (optional), eips (optional). Untested on this
# host against a real Kindle ash; --self-test runs on any POSIX sh.
#
#   sh voyage-probe-printk-recapture.sh --self-test

set -eu

OUT_NAME=/mnt/us/voyage-printk-recapture.txt
SCHEMA=voyage-printk-recapture-v1
MARKER=VOYAGE_PRINTK_RECAPTURE_DONE
MAX_BYTES=65536

# Strip syslog prefix "<n>[ stamp ] " if present; else leave the line as-is.
strip_prefix() {
	# shellcheck disable=SC2001
	printf '%s\n' "$1" | sed 's/^<[0-9][0-9]*>\[[[:space:]0-9.]*\][[:space:]]*//'
}

# Return 0 if the (already stripped) body looks like a unique identifier.
# Deliberately does NOT treat the fixed phrase "command line" as unique —
# that is the launcher bug this probe works around.
has_unique() {
	body=$1
	printf '%s' "$body" | grep -Ei \
		'board_id|(^|[^a-z])serial([^a-z]|=)|(^|[^a-z])ssid([^a-z]|=)|wlan0|eth0|iSerial|([0-9a-f]{2}:){5}[0-9a-f]{2}|([0-9a-f]{2}-){5}[0-9a-f]{2}' \
		>/dev/null 2>&1 && return 0
	# 12+ contiguous hex digits (MAC-without-separators / long ids).
	printf '%s' "$body" | grep -Ei '[0-9a-f]{12}' >/dev/null 2>&1 && return 0
	return 1
}

# Return 0 if this stripped body is an allowed diagnostic line.
is_allowed_body() {
	body=$1
	case "$body" in
		pw3-preinit:*) return 0 ;;
		pw3-handoff:*) return 0 ;;
		pw3-report-area:*) return 0 ;;
		pw3-init-check:*) return 0 ;;
		pw3-usb:*) return 0 ;;
		# Narrow trouble shapes (same spirit as userlog ALLOW); bodies still
		# face has_unique().
		'Unable to handle kernel'*) return 0 ;;
		'Internal error:'*) return 0 ;;
		'Kernel panic'*) return 0 ;;
		Oops*) return 0 ;;
		'BUG:'*) return 0 ;;
		'WARNING:'*) return 0 ;;
		Backtrace:*) return 0 ;;
		'Out of memory'*) return 0 ;;
		'page allocation failure'*) return 0 ;;
		'PC is at '*) return 0 ;;
		'LR is at '*) return 0 ;;
		'Modules linked in:'*) return 0 ;;
		PM:*) return 0 ;;
		'suspend debug'*) return 0 ;;
		mmcblk*) return 0 ;;
		'mxc_epdc'*) return 0 ;;
	esac
	return 1
}

# Emit one kept line, or nothing. Updates HIT_* via eval-friendly globals.
consider_line() {
	raw=$1
	[ -n "$raw" ] || return 0
	# Drop NULs / non-printable noise from the raw ring chunking.
	# Busybox tr may lack -cd with unicode; keep ASCII printable + tab.
	clean=$(printf '%s' "$raw" | tr -cd '\11\12\15\40-\176')
	[ -n "$clean" ] || return 0
	body=$(strip_prefix "$clean")
	[ -n "$body" ] || return 0

	# Hit booleans (never print the full Linux version line: may carry host).
	case "$body" in
		'Linux version 3.0.35-lab126-voyage-android81'*) HIT_LINUX_VOYAGE=1 ;;
		'Linux version 3.0.35-lab126-pw3-android81'*) HIT_LINUX_PW3=1 ;;
		'Linux version 3.0.35-lab126'*) HIT_LINUX_STOCKISH=1 ;;
	esac
	case "$body" in
		pw3-handoff:*'BEGIN release='*) HIT_HANDOFF_BEGIN=1 ;;
		pw3-handoff:*'RESULT skipped'*) HIT_HANDOFF_SKIPPED=1 ;;
		pw3-handoff:*'handing over'*) HIT_HANDOFF_END=1 ;;
		pw3-preinit:*'STOPPED in the new kernel'*) HIT_PREINIT_STOPPED=1 ;;
		pw3-preinit:*'configuration or complete command line rejected'*) HIT_PREINIT_CONF_REJECT=1 ;;
		pw3-preinit:*'PW3_TESTFILE_INIT_V10'*) HIT_PREINIT_CONTRACT=1 ;;
		pw3-preinit:*'unexpected kernel'*) HIT_PREINIT_UNEXPECT=1 ;;
		pw3-preinit:*'system and data test directories differ'*) HIT_PREINIT_DIR_DIFF=1 ;;
		pw3-preinit:*'test system image'*) HIT_PREINIT_IMAGE=1 ;;
		pw3-preinit:*'executing the original AOSP init'*) HIT_PREINIT_EXEC_INIT=1 ;;
		pw3-report-area:*) HIT_REPORT_AREA=1 ;;
	esac

	if ! is_allowed_body "$body"; then
		LEFT_OUT=$((LEFT_OUT + 1))
		return 0
	fi
	if has_unique "$body"; then
		LEFT_OUT=$((LEFT_OUT + 1))
		LEFT_OUT_UNIQUE=$((LEFT_OUT_UNIQUE + 1))
		return 0
	fi
	KEPT=$((KEPT + 1))
	printf 'kept=%s\n' "$body"
}

filter_ring_text() {
	# Read stdin (synthetic or printkbuf text). Do not store raw.
	KEPT=0
	LEFT_OUT=0
	LEFT_OUT_UNIQUE=0
	HIT_LINUX_VOYAGE=0
	HIT_LINUX_PW3=0
	HIT_LINUX_STOCKISH=0
	HIT_HANDOFF_BEGIN=0
	HIT_HANDOFF_SKIPPED=0
	HIT_HANDOFF_END=0
	HIT_PREINIT_STOPPED=0
	HIT_PREINIT_CONF_REJECT=0
	HIT_PREINIT_CONTRACT=0
	HIT_PREINIT_UNEXPECT=0
	HIT_PREINIT_DIR_DIFF=0
	HIT_PREINIT_IMAGE=0
	HIT_PREINIT_EXEC_INIT=0
	HIT_REPORT_AREA=0
	# Line-based; raw ring may interleave, same as launcher note.
	while IFS= read -r line || [ -n "$line" ]; do
		consider_line "$line"
	done
}

emit_report_from_text() {
	src_note=$1
	text=$2
	# Avoid a pipeline subshell so HIT_*/KEPT survive for the trailer.
	_syn=/tmp/voyage_printk_selftest_$$.txt
	printf '%s\n' "$text" > "$_syn"
	echo "schema=$SCHEMA"
	echo "privacy=allowlisted_pw3_and_trouble_lines_no_raw_ring"
	echo "note=no_board_id_mac_serial_no_report_bin_no_mem_no_module_no_handoff"
	echo "source=$src_note"
	echo "filter_bug_note=launcher_userlog_identifier_drops_pw3-preinit_lines_containing_substring_command_line"
	echo "uname_release=$(uname -r 2>/dev/null || echo unknown)"
	echo "---kept-lines---"
	filter_ring_text < "$_syn"
	rm -f "$_syn"
	echo "---counts---"
	echo "kept=$KEPT"
	echo "left_out=$LEFT_OUT"
	echo "left_out_unique=$LEFT_OUT_UNIQUE"
	echo "---hits---"
	echo "hit_linux_voyage_android81=$HIT_LINUX_VOYAGE"
	echo "hit_linux_pw3_android81=$HIT_LINUX_PW3"
	echo "hit_linux_lab126_other=$HIT_LINUX_STOCKISH"
	echo "hit_handoff_begin=$HIT_HANDOFF_BEGIN"
	echo "hit_handoff_skipped=$HIT_HANDOFF_SKIPPED"
	echo "hit_handoff_end=$HIT_HANDOFF_END"
	echo "hit_preinit_stopped=$HIT_PREINIT_STOPPED"
	echo "hit_preinit_conf_rejected=$HIT_PREINIT_CONF_REJECT"
	echo "hit_preinit_contract=$HIT_PREINIT_CONTRACT"
	echo "hit_preinit_image_msg=$HIT_PREINIT_IMAGE"
	echo "hit_preinit_exec_init=$HIT_PREINIT_EXEC_INIT"
	echo "hit_report_area=$HIT_REPORT_AREA"
	if [ "$HIT_PREINIT_STOPPED" -eq 1 ] && [ "$HIT_PREINIT_CONF_REJECT" -eq 0 ] \
		&& [ "$HIT_PREINIT_IMAGE" -eq 0 ] && [ "$HIT_PREINIT_EXEC_INIT" -eq 0 ]; then
		echo "warning=stopped_without_specific_reason_in_kept_set"
	fi
	echo "result: complete"
	echo "$MARKER"
}

self_test() {
	fail=0
	# Synthetic ring: includes the exact PreInit stop reason the launcher drops,
	# plus unique-id bait that must never appear in the report body.
	mac='aa:bb:cc:dd:ee:ff'
	serial='B0XXXXXXXXXXXXXX'
	synth=$(printf '%s\n' \
		'<6>[    0.000000] Linux version 3.0.35-lab126-voyage-android81 (builder@host) (gcc) #1' \
		'<3>[    0.450000] pw3-handoff: BEGIN release=3.0.35-lab126-voyage-android81 uptime=0.45 mounts=111' \
		'<3>[    0.450000] pw3-handoff: RESULT skipped: unexpected kernel or mounts' \
		'<3>[    0.450000] pw3-handoff: END uptime=0.45 handing over to /pw3-testfile-init.real' \
		'<3>[    0.500000] pw3-preinit: PW3_TESTFILE_INIT_V10_DM_CLUSTER_EXTENTS_FAT_RO_KEPT_DATA_SIZED_IMAGES_SYSTEM_STAMP_BACKGROUND_RECHECK_FAT_CROSSLINK_OPTIONAL_REPORT_AREA_IMAGE_OWNS_APP_CODE_THREE_KEY_CMDLINE_NO_PARTITIONING' \
		'<3>[    0.510000] pw3-preinit: testfile configuration or complete command line rejected' \
		'<3>[    0.520000] pw3-preinit: STOPPED in the new kernel; the device restarts itself back to the stock system.' \
		"<6>[    1.000000] usb0: MAC $mac" \
		"<5>[    1.100000] Kernel command line: console=ttymxc0 serial=$serial" \
		'<6>[    2.000000] ath6kl: connected to ssid HomeNetwork' \
		'<6>[    3.000000] unrelated noise line about weather')
	out=$(emit_report_from_text 'self-test-synthetic' "$synth")

	printf '%s\n' "$out" | grep -q "schema=$SCHEMA" || { echo 'self-test: schema'; fail=1; }
	printf '%s\n' "$out" | grep -q "$MARKER" || { echo 'self-test: marker'; fail=1; }
	printf '%s\n' "$out" | grep -q 'hit_preinit_conf_rejected=1' || {
		echo 'self-test: conf-reject hit missing (the launcher bug case)'; fail=1; }
	printf '%s\n' "$out" | grep -q 'hit_preinit_stopped=1' || { echo 'self-test: stopped hit'; fail=1; }
	printf '%s\n' "$out" | grep -q 'hit_handoff_skipped=1' || { echo 'self-test: skip hit'; fail=1; }
	printf '%s\n' "$out" | grep -q 'hit_linux_voyage_android81=1' || {
		echo 'self-test: linux voyage hit'; fail=1; }
	printf '%s\n' "$out" | grep -F -q 'kept=pw3-preinit: testfile configuration or complete command line rejected' || {
		echo 'self-test: stop reason line not kept'; fail=1; }
	printf '%s\n' "$out" | grep -F -q "$mac" && { echo 'self-test: mac leaked'; fail=1; }
	printf '%s\n' "$out" | grep -F -q "$serial" && { echo 'self-test: serial leaked'; fail=1; }
	printf '%s\n' "$out" | grep -F -q 'ssid HomeNetwork' && { echo 'self-test: ssid leaked'; fail=1; }
	printf '%s\n' "$out" | grep -F -q 'builder@host' && { echo 'self-test: linux banner body leaked'; fail=1; }
	printf '%s\n' "$out" | grep -F -q 'unrelated noise' && { echo 'self-test: noise kept'; fail=1; }
	printf '%s\n' "$out" | grep -q 'left_out_unique=' || { echo 'self-test: unique count'; fail=1; }

	if [ "$fail" -ne 0 ]; then
		echo "self-test FAILED"
		return 1
	fi
	echo "self-test ok"
	return 0
}

if [ "${1:-}" = "--self-test" ]; then
	self_test
	exit $?
fi

# --- device path ---
if [ ! -r /proc/printkbuf ]; then
	tmpout=/tmp/voyage_printk_recapture_$$.txt
	{
		echo "schema=$SCHEMA"
		echo "privacy=allowlisted_pw3_and_trouble_lines_no_raw_ring"
		echo "source=/proc/printkbuf"
		echo "result: absent"
		echo "error=printkbuf_unreadable"
		echo "errno_note=open_or_read_failed"
		echo "$MARKER"
	} > "$tmpout"
	if cp -f "$tmpout" "$OUT_NAME" 2>/dev/null; then
		rm -f "$tmpout"
		if command -v eips >/dev/null 2>&1; then
			eips 1 24 "printk capture" 2>/dev/null || true
			eips 1 25 "absent" 2>/dev/null || true
		fi
		exit 0
	fi
	rm -f "$tmpout"
	if command -v eips >/dev/null 2>&1; then
		eips 1 24 "printk capture" 2>/dev/null || true
		eips 1 25 "write failed" 2>/dev/null || true
	fi
	exit 1
fi

# Bound the read: ring is ~32KiB; never dump unbounded.
tmpraw=/tmp/voyage_printk_raw_$$.bin
tmpout=/tmp/voyage_printk_recapture_$$.txt
# dd is on stock Kindle; if missing, fall back to head -c via busybox.
if dd if=/proc/printkbuf of="$tmpraw" bs=4096 count=16 2>/dev/null; then
	:
elif head -c "$MAX_BYTES" /proc/printkbuf > "$tmpraw" 2>/dev/null; then
	:
else
	cat /proc/printkbuf > "$tmpraw" 2>/dev/null || true
fi
# Convert to line-ish text without preserving the binary file as an artifact.
# tr drops NULs so read loops terminate; raw file is deleted immediately after.
tmptxt=/tmp/voyage_printk_txt_$$.txt
tr -cd '\11\12\15\40-\176' < "$tmpraw" > "$tmptxt" || true
rm -f "$tmpraw"
bytes=$(wc -c < "$tmptxt" | tr -d ' ')

{
	echo "schema=$SCHEMA"
	echo "privacy=allowlisted_pw3_and_trouble_lines_no_raw_ring"
	echo "note=no_board_id_mac_serial_no_report_bin_no_mem_no_module_no_handoff"
	echo "source=/proc/printkbuf (raw ring, not in order; text extract only)"
	echo "filter_bug_note=launcher_userlog_identifier_drops_pw3-preinit_lines_containing_substring_command_line"
	echo "extract_bytes=$bytes"
	echo "uname_release=$(uname -r 2>/dev/null || echo unknown)"
	echo "---kept-lines---"
	# Re-run filter with side-effect prints; reset counters via subshell vars.
	KEPT=0; LEFT_OUT=0; LEFT_OUT_UNIQUE=0
	HIT_LINUX_VOYAGE=0; HIT_LINUX_PW3=0; HIT_LINUX_STOCKISH=0
	HIT_HANDOFF_BEGIN=0; HIT_HANDOFF_SKIPPED=0; HIT_HANDOFF_END=0
	HIT_PREINIT_STOPPED=0; HIT_PREINIT_CONF_REJECT=0; HIT_PREINIT_CONTRACT=0
	HIT_PREINIT_UNEXPECT=0; HIT_PREINIT_DIR_DIFF=0; HIT_PREINIT_IMAGE=0
	HIT_PREINIT_EXEC_INIT=0; HIT_REPORT_AREA=0
	while IFS= read -r line || [ -n "$line" ]; do
		consider_line "$line"
	done < "$tmptxt"
	echo "---counts---"
	echo "kept=$KEPT"
	echo "left_out=$LEFT_OUT"
	echo "left_out_unique=$LEFT_OUT_UNIQUE"
	echo "---hits---"
	echo "hit_linux_voyage_android81=$HIT_LINUX_VOYAGE"
	echo "hit_linux_pw3_android81=$HIT_LINUX_PW3"
	echo "hit_linux_lab126_other=$HIT_LINUX_STOCKISH"
	echo "hit_handoff_begin=$HIT_HANDOFF_BEGIN"
	echo "hit_handoff_skipped=$HIT_HANDOFF_SKIPPED"
	echo "hit_handoff_end=$HIT_HANDOFF_END"
	echo "hit_preinit_stopped=$HIT_PREINIT_STOPPED"
	echo "hit_preinit_conf_rejected=$HIT_PREINIT_CONF_REJECT"
	echo "hit_preinit_contract=$HIT_PREINIT_CONTRACT"
	echo "hit_preinit_image_msg=$HIT_PREINIT_IMAGE"
	echo "hit_preinit_exec_init=$HIT_PREINIT_EXEC_INIT"
	echo "hit_report_area=$HIT_REPORT_AREA"
	if [ "$HIT_PREINIT_STOPPED" -eq 1 ] && [ "$HIT_PREINIT_CONF_REJECT" -eq 0 ] \
		&& [ "$HIT_PREINIT_IMAGE" -eq 0 ] && [ "$HIT_PREINIT_EXEC_INIT" -eq 0 ]; then
		echo "warning=stopped_without_specific_reason_in_kept_set"
	fi
	if [ "$bytes" -eq 0 ]; then
		echo "result: partial"
		echo "error=empty_extract"
	else
		echo "result: complete"
	fi
	echo "$MARKER"
} > "$tmpout"
rm -f "$tmptxt"

# Refuse to publish if a unique token slipped through.
if grep -Ei 'board_id|(^|[^a-z])serial=|ssid |wlan0|eth0|([0-9a-f]{2}:){5}[0-9a-f]{2}' "$tmpout" \
	| grep -v '^filter_bug_note=' | grep -v '^privacy=' | grep -v '^note=' >/dev/null 2>&1; then
	rm -f "$tmpout"
	if command -v eips >/dev/null 2>&1; then
		eips 1 24 "printk capture" 2>/dev/null || true
		eips 1 25 "refused" 2>/dev/null || true
	fi
	exit 2
fi

if cp -f "$tmpout" "$OUT_NAME" 2>/dev/null; then
	rm -f "$tmpout"
	result=$(grep '^result: ' "$OUT_NAME" 2>/dev/null | head -n 1)
	if command -v eips >/dev/null 2>&1; then
		eips 1 24 "printk capture" 2>/dev/null || true
		case "$result" in
			"result: complete") eips 1 25 "complete" 2>/dev/null || true ;;
			"result: partial") eips 1 25 "partial" 2>/dev/null || true ;;
			*) eips 1 25 "done" 2>/dev/null || true ;;
		esac
	fi
	exit 0
fi
rm -f "$tmpout"
if command -v eips >/dev/null 2>&1; then
	eips 1 24 "printk capture" 2>/dev/null || true
	eips 1 25 "write failed" 2>/dev/null || true
fi
exit 1
