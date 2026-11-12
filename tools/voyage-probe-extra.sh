#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Second read-only probe for the Voyage handoff fields that are still empty.
# Place as /mnt/us/RUNME.sh, eject, then on the Kindle: ;log runme
# Writes only /mnt/us/voyage-probe-extra.txt and two short eips lines.
# Does not mount, remount, insmod, write a block device, run Readom, use the
# network, read kernel memory, or read books, accounts, Wi-Fi secrets, MAC,
# serial, or board id.
#
#   sh voyage-probe-extra.sh --self-test
#
# This file contains no real device serial, MAC, or IP address.

OUT_NAME=/mnt/us/voyage-probe-extra.txt

note_withheld() {
	key="$1"
	case ",${WITHHELD}," in
		*,$key,*) ;;
		*)
			if [ -n "$WITHHELD" ]; then
				WITHHELD="${WITHHELD},${key}"
			else
				WITHHELD="$key"
			fi
			;;
	esac
}

note_error() {
	ERRORS=$((ERRORS + 1))
	echo "error: $1"
}

is_addr() {
	printf '%s' "$1" | grep -Eq '^(0x[0-9A-Fa-f]{1,8}|[0-9]{1,10})$'
}

is_ip_mode() {
	v=$(printf '%s' "$1" | tr 'A-Z' 'a-z')
	case "$v" in
		off|none|on|dhcp) return 0 ;;
	esac
	return 1
}

is_bin_path() {
	printf '%s' "$1" | grep -Eq '^/(opt/ar6k|lib/firmware)/[A-Za-z0-9._/-]{1,160}\.bin$'
}

is_loop_backing() {
	printf '%s' "$1" | grep -Eq '^/dev/mmcblk0(p[1-4])?$'
}

is_decimal() {
	printf '%s' "$1" | grep -Eq '^[0-9]{1,20}$'
}

# Rebuild a command line from allow-listed tokens. Never prints $1.
filter_cmdline() {
	raw="$1"
	KEPT=""
	WITHHELD=""
	if [ -z "$raw" ]; then
		echo "cmdline_kept:"
		echo "cmdline_withheld_keys: (unreadable)"
		return 1
	fi
	set -f
	oldifs=$IFS
	IFS=' '
	# shellcheck disable=SC2086
	set -- $raw
	IFS=$oldifs
	set +f
	for tok in "$@"; do
		case "$tok" in
			log_pos_goal=*)
				val=${tok#*=}
				if is_addr "$val"; then
					KEPT="${KEPT:+$KEPT }log_pos_goal=$val"
				else
					note_withheld log_pos_goal
				fi
				;;
			ip=*)
				val=${tok#*=}
				if is_ip_mode "$val"; then
					mode=$(printf '%s' "$val" | tr 'A-Z' 'a-z')
					KEPT="${KEPT:+$KEPT }ip=$mode"
				else
					note_withheld ip
				fi
				;;
			console=*)
				val=${tok#*=}
				if printf '%s' "$val" | grep -Eq '^ttymxc[0-9],[0-9]{2,6}$'; then
					KEPT="${KEPT:+$KEPT }console=$val"
				else
					note_withheld console
				fi
				;;
			video=*)
				val=${tok#*=}
				if [ "$val" = "mxcepdcfb:E60,bpp=8,x_mem=3M" ]; then
					KEPT="${KEPT:+$KEPT }video=$val"
				else
					note_withheld video
				fi
				;;
			root=*)
				val=${tok#*=}
				if printf '%s' "$val" | grep -Eq '^/dev/mmcblk0p[1-4]$'; then
					KEPT="${KEPT:+$KEPT }root=$val"
				else
					note_withheld root
				fi
				;;
			rootwait|ro|rw|quiet)
				KEPT="${KEPT:+$KEPT }$tok"
				;;
			*=*)
				note_withheld "${tok%%=*}"
				;;
			*)
				note_withheld "flag"
				;;
		esac
	done
	echo "cmdline_kept: $KEPT"
	if [ -n "$WITHHELD" ]; then
		echo "cmdline_withheld_keys: $WITHHELD"
	else
		echo "cmdline_withheld_keys: (none)"
	fi
	return 0
}

read_one_line() {
	# $1 path. Prints the first line with CR/LF removed, or fails.
	if [ ! -r "$1" ]; then
		return 1
	fi
	IFS= read -r line < "$1" || return 1
	printf '%s' "$line" | tr -d '\r'
}

emit_report() {
	base="$1"
	ERRORS=0
	echo "VOYAGE_READONLY_PROBE_EXTRA"
	echo "generated: $(date 2>/dev/null || echo unknown)"
	echo ""
	echo "== id =="
	if command -v id >/dev/null 2>&1; then
		id 2>/dev/null || echo "id: failed"
	else
		echo "id: not available"
		note_error "id not available"
	fi
	echo ""

	echo "== cmdline (allow-listed tokens only; raw line not written) =="
	echo "log_pos_goal_class: printk buffer physical address, not an identity field"
	echo "ip_class: mode constant only (off, none, on, dhcp)"
	cmdf="$base/proc/cmdline"
	if [ -r "$cmdf" ]; then
		cmd=$(tr '\0' ' ' < "$cmdf" 2>/dev/null || true)
		filter_cmdline "$cmd" || note_error "cmdline empty"
		cmd=""
	else
		echo "cmdline_kept:"
		echo "cmdline_withheld_keys: (unreadable)"
		note_error "cannot read cmdline"
	fi
	echo ""

	echo "== bootmode =="
	bm="$base/proc/bootmode"
	if [ -r "$bm" ]; then
		mode=$(read_one_line "$bm" || true)
		case "$mode" in
			main|diags) echo "bootmode: $mode" ;;
			"") note_error "bootmode empty"; echo "bootmode: withheld (empty)" ;;
			*) echo "bootmode: withheld (not main or diags)" ;;
		esac
	else
		echo "bootmode: unreadable"
		note_error "cannot read bootmode"
	fi
	echo ""

	echo "== machine id =="
	echo "machine_id: not collected"
	echo "machine_id_why: no proc file publishes only the numeric machine id. /proc/atags also carries the board id and MAC, so it is not read. The mach-types number is not a measurement."
	echo ""

	echo "== block start and size =="
	echo "unit: sysfs size and start are 512-byte sectors. start is not read for the whole disk or the boot nodes."
	for name in mmcblk0 mmcblk0p1 mmcblk0p2 mmcblk0p3 mmcblk0p4 mmcblk0boot0 mmcblk0boot1; do
		dir="$base/sys/class/block/$name"
		if [ ! -d "$dir" ]; then
			echo "$name: absent"
			continue
		fi
		sz=$(read_one_line "$dir/size" || true)
		if is_decimal "$sz"; then
			line="$name size=$sz"
		else
			line="$name size=unreadable"
			note_error "bad size for $name"
		fi
		case "$name" in
			mmcblk0p*)
				st=$(read_one_line "$dir/start" || true)
				if is_decimal "$st"; then
					line="$line start=$st"
				else
					line="$line start=unreadable"
					note_error "bad start for $name"
				fi
				;;
		esac
		echo "$line"
	done
	echo ""

	echo "== user FAT loop =="
	loop="$base/sys/block/loop0/loop"
	if [ -d "$loop" ]; then
		back=$(read_one_line "$loop/backing_file" || true)
		off=$(read_one_line "$loop/offset" || true)
		lim=$(read_one_line "$loop/sizelimit" || true)
		if is_loop_backing "$back"; then
			echo "backing_file: $back"
		else
			echo "backing_file: withheld (not /dev/mmcblk0 or /dev/mmcblk0p1-4)"
			note_error "loop backing not allow-listed"
		fi
		if is_decimal "$off"; then
			echo "offset: $off"
		else
			echo "offset: unreadable"
			note_error "loop offset"
		fi
		if is_decimal "$lim"; then
			echo "sizelimit: $lim"
		else
			echo "sizelimit: unreadable"
			note_error "loop sizelimit"
		fi
	else
		echo "loop0: absent"
		note_error "loop0 absent"
	fi
	mf="$base/proc/mounts"
	if [ -r "$mf" ]; then
		found=0
		while IFS= read -r mline || [ -n "$mline" ]; do
			set -f
			oldifs=$IFS
			IFS=' '
			# shellcheck disable=SC2086
			set -- $mline
			IFS=$oldifs
			set +f
			src=$1
			tgt=$2
			typ=$3
			if [ "$tgt" = "/mnt/base-us" ]; then
				found=1
				case "$src" in
					/dev/loop0|/dev/loop/0)
						if [ "$typ" = "vfat" ]; then
							echo "user_mount: /mnt/base-us source=$src type=vfat"
						else
							echo "user_mount: withheld (not vfat)"
						fi
						;;
					*) echo "user_mount: withheld (not the loop device)" ;;
				esac
			fi
		done < "$mf"
		if [ "$found" -eq 0 ]; then
			echo "user_mount: /mnt/base-us not in mounts"
		fi
	else
		echo "mounts: unreadable"
		note_error "cannot read mounts"
	fi
	echo ""

	echo "== wifi driver and firmware paths =="
	echo "values are paths and file sizes only. file contents are not read."
	for mod in ar6000 ath6kl_sdio ath6kl; do
		if [ -d "$base/sys/module/$mod" ]; then
			echo "module: $mod present"
		else
			echo "module: $mod absent"
		fi
		param="$base/sys/module/$mod/parameters/board_data_file"
		if [ -r "$param" ]; then
			pval=$(read_one_line "$param" || true)
			if is_bin_path "$pval"; then
				echo "board_data_file: $mod $pval"
				if [ -f "$base$pval" ]; then
					echo "board_data_file_bytes: $(wc -c < "$base$pval" | tr -d ' ')"
				else
					echo "board_data_file_bytes: absent"
				fi
			else
				echo "board_data_file: $mod withheld (not an allow-listed path)"
			fi
		fi
	done
	for cand in \
		/opt/ar6k/target/AR6003/hw2.1.1/bin/AR6803_default.bin \
		/opt/ar6k/target/AR6003/hw2.1.1/bin/AR6003_wfo_calfile.bin \
		/opt/ar6k/target/AR6003/hw2.1.1/bin/fw-4.bin \
		/opt/ar6k/target/AR6003/hw2.1.1/bin/athwlan.bin
	do
		if [ -f "$base$cand" ]; then
			echo "candidate: $cand bytes=$(wc -c < "$base$cand" | tr -d ' ')"
		else
			echo "candidate: $cand absent"
		fi
	done
	wifim="$base/etc/upstart/wifim"
	if [ -f "$wifim" ]; then
		echo "wifim: paths only"
		while IFS= read -r wline || [ -n "$wline" ]; do
			set -f
			oldifs=$IFS
			IFS=' '
			# shellcheck disable=SC2086
			set -- $wline
			IFS=$oldifs
			set +f
			for wtok in "$@"; do
				case "$wtok" in
					*=*) wval=${wtok#*=} ;;
					*) wval=$wtok ;;
				esac
				if is_bin_path "$wval"; then
					echo "wifim_path: $wval"
				fi
			done
		done < "$wifim"
	else
		echo "wifim: absent"
	fi
	echo ""

	echo "== result =="
	if [ "$ERRORS" -eq 0 ]; then
		echo "result: complete"
	else
		echo "result: partial"
	fi
	echo "errors: $ERRORS"
	echo "VOYAGE_PROBE_EXTRA_DONE"
}

self_test() {
	fail=0
	tmp=$(mktemp -d)
	serial=$(printf '%s%s' 'G0' '00123456789012')
	mac=$(printf '%s:%s:%s:%s:%s:%s' aa bb cc dd ee ff)
	ipaddr=$(printf '%s.%s.%s.%s' 192 168 0 1)
	badpath=$(printf '%s/%s' /tmp 'not-a-block')

	mkdir -p "$tmp/proc" "$tmp/sys/class/block/mmcblk0" \
		"$tmp/sys/class/block/mmcblk0p1" "$tmp/sys/class/block/mmcblk0p4" \
		"$tmp/sys/block/loop0/loop" \
		"$tmp/sys/module/ar6000/parameters" \
		"$tmp/opt/ar6k/target/AR6003/hw2.1.1/bin" \
		"$tmp/etc/upstart"
	printf 'rootwait log_pos_goal=0x80001000 console=ttymxc0,115200 root=/dev/mmcblk0p1 ro ip=off quiet video=mxcepdcfb:E60,bpp=8,x_mem=3M serial=%s mac=%s\n' \
		"$serial" "$mac" > "$tmp/proc/cmdline"
	printf 'main\n' > "$tmp/proc/bootmode"
	printf '/dev/loop/0 /mnt/base-us vfat rw 0 0\n/dev/mmcblk0p1 / ext3 ro 0 0\n' > "$tmp/proc/mounts"
	printf '7733248\n' > "$tmp/sys/class/block/mmcblk0/size"
	printf '921600\n' > "$tmp/sys/class/block/mmcblk0p1/size"
	printf '65536\n' > "$tmp/sys/class/block/mmcblk0p1/start"
	printf '6385664\n' > "$tmp/sys/class/block/mmcblk0p4/size"
	printf '1249280\n' > "$tmp/sys/class/block/mmcblk0p4/start"
	printf '/dev/mmcblk0p4\n' > "$tmp/sys/block/loop0/loop/backing_file"
	printf '8192\n' > "$tmp/sys/block/loop0/loop/offset"
	printf '0\n' > "$tmp/sys/block/loop0/loop/sizelimit"
	cal="$tmp/opt/ar6k/target/AR6003/hw2.1.1/bin/AR6803_default.bin"
	dd if=/dev/zero of="$cal" bs=2048 count=1 2>/dev/null
	printf '%s\n' "$cal" | sed "s|^$tmp||" > "$tmp/sys/module/ar6000/parameters/board_data_file"
	printf 'board=%s secret=%s\n' \
		/opt/ar6k/target/AR6003/hw2.1.1/bin/fw-4.bin "$serial" > "$tmp/etc/upstart/wifim"
	: > "$tmp/opt/ar6k/target/AR6003/hw2.1.1/bin/fw-4.bin"

	out=$(emit_report "$tmp")
	printf '%s\n' "$out" | grep -q 'VOYAGE_PROBE_EXTRA_DONE' || { echo 'self-test: no done marker'; fail=1; }
	printf '%s\n' "$out" | grep -q 'result: complete' || { echo 'self-test: expected complete'; fail=1; }
	printf '%s\n' "$out" | grep -q 'log_pos_goal=0x80001000' || { echo 'self-test: address dropped'; fail=1; }
	printf '%s\n' "$out" | grep -q 'ip=off' || { echo 'self-test: ip mode dropped'; fail=1; }
	printf '%s\n' "$out" | grep -q 'bootmode: main' || { echo 'self-test: bootmode dropped'; fail=1; }
	printf '%s\n' "$out" | grep -q 'mmcblk0p1 size=921600 start=65536' || { echo 'self-test: partition start dropped'; fail=1; }
	printf '%s\n' "$out" | grep -q 'backing_file: /dev/mmcblk0p4' || { echo 'self-test: backing dropped'; fail=1; }
	printf '%s\n' "$out" | grep -q 'offset: 8192' || { echo 'self-test: offset dropped'; fail=1; }
	printf '%s\n' "$out" | grep -q 'board_data_file_bytes: 2048' || { echo 'self-test: cal size dropped'; fail=1; }
	printf '%s\n' "$out" | grep -q 'wifim_path: /opt/ar6k/target/AR6003/hw2.1.1/bin/fw-4.bin' || { echo 'self-test: wifim path dropped'; fail=1; }
	printf '%s\n' "$out" | grep -q 'machine_id: not collected' || { echo 'self-test: machine id was invented'; fail=1; }
	printf '%s\n' "$out" | grep -F -q "$serial" && { echo 'self-test: serial leaked'; fail=1; }
	printf '%s\n' "$out" | grep -F -q "$mac" && { echo 'self-test: mac leaked'; fail=1; }
	printf '%s\n' "$out" | grep -F -q '4091' && { echo 'self-test: source machine id leaked as a reading'; fail=1; }

	# Redaction and absence. A second tree, not a device.
	tmp2=$(mktemp -d)
	mkdir -p "$tmp2/proc" "$tmp2/sys/block/loop0/loop" "$tmp2/sys/module/ar6000/parameters"
	printf 'log_pos_goal=not-an-address ip=%s console=evil video=secret root=/tmp/x %s\n' \
		"$ipaddr" "$serial" > "$tmp2/proc/cmdline"
	printf '%s\n' "$serial" > "$tmp2/proc/bootmode"
	printf '%s\n' "$badpath" > "$tmp2/sys/block/loop0/loop/backing_file"
	printf 'nope\n' > "$tmp2/sys/block/loop0/loop/offset"
	printf '0\n' > "$tmp2/sys/block/loop0/loop/sizelimit"
	printf '%s\n' "$badpath" > "$tmp2/sys/module/ar6000/parameters/board_data_file"
	out2=$(emit_report "$tmp2")
	printf '%s\n' "$out2" | grep -q 'result: partial' || { echo 'self-test: expected partial'; fail=1; }
	printf '%s\n' "$out2" | grep -q 'VOYAGE_PROBE_EXTRA_DONE' || { echo 'self-test: partial has no marker'; fail=1; }
	printf '%s\n' "$out2" | grep -q 'cmdline_withheld_keys: log_pos_goal,ip,console,video,root,flag' || {
		echo 'self-test: withheld keys mismatch'; fail=1; }
	printf '%s\n' "$out2" | grep -q 'bootmode: withheld' || { echo 'self-test: bad bootmode kept'; fail=1; }
	printf '%s\n' "$out2" | grep -q 'backing_file: withheld' || { echo 'self-test: bad backing kept'; fail=1; }
	printf '%s\n' "$out2" | grep -q 'board_data_file: ar6000 withheld' || { echo 'self-test: bad wifi path kept'; fail=1; }
	printf '%s\n' "$out2" | grep -F -q "$ipaddr" && { echo 'self-test: ip address leaked'; fail=1; }
	printf '%s\n' "$out2" | grep -F -q "$serial" && { echo 'self-test: serial leaked from second tree'; fail=1; }
	printf '%s\n' "$out2" | grep -F -q 'not-an-address' && { echo 'self-test: rejected address leaked'; fail=1; }
	printf '%s\n' "$out2" | grep -F -q "$badpath" && { echo 'self-test: rejected path leaked'; fail=1; }

	rm -rf "$tmp" "$tmp2"
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

# Device path. ROOT is empty: reads the real proc and sys.
tmpout=/tmp/voyage_probe_extra_$$.txt
if ! emit_report "" > "$tmpout" 2>&1; then
	:
fi
result=$(grep '^result: ' "$tmpout" 2>/dev/null | head -n 1)
if cp -f "$tmpout" "$OUT_NAME" 2>/dev/null; then
	rm -f "$tmpout"
	if command -v eips >/dev/null 2>&1; then
		eips 1 24 "extra probe" 2>/dev/null || true
		case "$result" in
			"result: complete") eips 1 25 "complete" 2>/dev/null || true ;;
			*) eips 1 25 "partial" 2>/dev/null || true ;;
		esac
	fi
	exit 0
fi
rm -f "$tmpout"
if command -v eips >/dev/null 2>&1; then
	eips 1 24 "extra probe" 2>/dev/null || true
	eips 1 25 "write failed" 2>/dev/null || true
fi
exit 1
