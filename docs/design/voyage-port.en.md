# Voyage port: what is done, and what blocks installation

This is not an "it installs" note. The entry build refuses to pack a release while `installable` is not true. The Paperwhite 3 profile stays at `boot/profiles/pw3-5.16.2.1.1.json` with `installable: false`, as history. Chinese: `voyage-port.md`.

## Checked against official files

Downloaded and hashed on 2026-11-12. The numbers live in `source-lock.json` under `voyage_kernel` and in `source` inside `boot/profiles/voyage-5.13.6.json`. A test checks that the two copies match.

| File | Result |
|---|---|
| `Kindle_src_5.13.6_3731990038.tar.gz` | 332,761,879 bytes, `4a01245d…c2222f` |
| member `gplrelease/linux-3.0.35.tar.gz` | 121,872,729 bytes, `a66a58b8…5144b0` |
| `update_kindle_voyage_5.13.6.bin` | 247,461,749 bytes, `80856a11…7a155b`, magic `SP01` |

`BUILD_HOW-TO.txt` in that member says Voyage uses `imx60_wario_defconfig`. That defconfig turns on `CONFIG_VMSPLIT_3G`, `CONFIG_PAGE_OFFSET=0xC0000000`, `CONFIG_MX6SL_WARIO_BASE`, `CONFIG_ATH6KL=m` and `CONFIG_ATH6KL_SDIO=m`. `arch/arm/tools/mach-types` numbers `mx6sl_wario` as 4091. That is a source fact. It is **not** copied into `measured.machine_id` and it is not enough to hand off.

`arch/arm/plat-mxc/include/mach/memory.h` defines both `MX6SL_PHYS_OFFSET` (0x80000000) and, under `CONFIG_ARCH_MX6`, `MX6_PHYS_OFFSET` (0x10000000). `board-mx6sl_wario.c` uses the former for `boot_params`. The handoff adopts neither address.

The same day, `tools/apply-patch-series.py` applied all **85** patches under `patches/*.patch` and `patches/android-core/*.patch` to a fresh tree of this member, with **0** failures. `imx60_wario_defconfig` from that tree, plus `config/android-core.config` and a temporary Voyage fragment (`LOCALVERSION=-lab126-voyage-android81`, `ARCH_MMAP_RND_BITS=16`, `LAB126_ANDROID_ATH6KL_FIRMWARE=y`), then passed `merge-kconfig.py --check` with all **147** requested options present.

`uImage` was not produced with this machine's `arm-linux-gnueabi-gcc` 13.3. The 3.0 tree has no `compiler-gcc13.h`. After a header that existed only in the temporary tree, the assembler stopped at `arch/arm/mm/proc-v7.S:445` (`junk at end of line, first unrecognized character is '#'`). The compiler this repository pins is AOSP gcc 4.9, which is not on this machine. The kernel patch series was not changed to appease gcc 13. That is an unfinished compile, not a device result.

The official `update.bin` has no squashfs magic and no plaintext `Linux version` or `eips`. The `1f 8b` bytes at offset 30755 are not a gzip stream. uname, the eips hash and the partition table were not extracted. The signature was not stripped and no partition was written.

## Missing, so installation is refused

Every key in `measured` is null: `eips_sha256`, `eips_bytes`, `uname_release`, `uname_version`, `machine_id`, `stock_cmdline`, `ram`, `partition_table`, `stock_functions`.

`tools/voyage_profile.py` runs from `boot/build_entry.py`, from `boot/build_launcher.py` when building an installer, and from `boot/build_module.py`. If any required field is empty, or if a Voyage measurement repeats the Paperwhite 3 eips hash, uname string, command line or kernel-function record, the build exits. At run time `CHECK_PROFILE == 3` logs and stops on E105 before the module is loaded and before `install()`. `dd_voyage_5_13_6.identity_ready` is 0, so `dd_device_matches` returns before comparing strings.

## Space (estimate)

The system image stays 512 MiB. The data image is 1024 MiB, format 2. With the 64 MiB reserve, an install needs **1600 MiB free**. The reason, and the fact that none of this was measured on a Voyage, is in `device/amazon/pw3/BoardConfig.mk`. The 512 MB heap settings were not changed: those numbers were measured on a PW3 of the same SoC family, and changing them without a new measurement is not an optimization.

## What to read off a device, and nothing else

Do not run `Readom.sh`, do not sign in, and do not copy a serial number, a MAC address or a Wi-Fi name. Strip those fields from the output before sending it back.

```sh
uname -a
sed -n '1,5p' /proc/version
grep -E 'Hardware|Revision' /proc/cpuinfo
wc -c /usr/sbin/eips; sha256sum /usr/sbin/eips
tr '\0' '\n' < /proc/cmdline
awk '$1=="System" || /System RAM/' /proc/iomem
awk '$4 ~ /mmcblk0/ {print}' /proc/partitions
cat /sys/class/block/mmcblk0/size
for b in mmcblk0 mmcblk0p1 mmcblk0p2 mmcblk0p3 mmcblk0p4 mmcblk0boot0 mmcblk0boot1; do
  echo "$b $(cat /sys/class/block/$b/ro 2>/dev/null) $(cat /sys/class/block/$b/size 2>/dev/null)"
done
df -k /mnt/us /mnt/base-us
```

The kernel function-body hashes (`pm_test_show`, `l2x0_flush_all`, `l2x0_disable`, `l2x0_inv_all`) have to be computed from the official kernel image that matches the `uname` above, not from the Paperwhite 3 record. Until then the handoff module should not be built.
