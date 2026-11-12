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

Host gcc 13.3 cannot build this 3.0 tree (`proc-v7.S` and `#`). The pinned AOSP gcc 4.9 was checked out instead, from `https://android.googlesource.com/platform/prebuilts/gcc/linux-x86/arm/arm-linux-androideabi-4.9` at `0390252b6bcc6217966ade31d07f8b12f6f78f89` (`git rev-parse` matches `revision` in `source-lock.json`). `git archive` of that commit does not hash to `archive_sha256`: that pin is an unpublished packing, so the git revision is the source that was verified. The kernel patch series was not changed.

That compiler, `imx60_wario_defconfig` and the 147-option config produced a kernel. `include/generated/utsrelease.h` is `3.0.35-lab126-voyage-android81+`. The trailing `+` is because the patched tree is dirty relative to the git commit made before the patches, not a release name. The compile command passes `-msoft-float`. This is a compile, not a boot.

| Artifact | SHA-256 |
|---|---|
| `zImage` | `bfc22d8738da550af66e378618083eaf7e24e579962dc4e6511c13fd42a1b735` |
| `uImage` | `8fe014996a74ae8215fa0dbe20992175a5d154054baa62e75f4d2e41a068e89d` |

The uImage load address is `0x80008000`. That is what this build wrote into the header. The same day's `/proc/iomem` on the device has one System RAM line, `80000000-9fffffff`: 512 MiB starting at `MX6SL_PHYS_OFFSET`. That range can be stored in `measured.ram`. It matches the PW3 record because the device reported it.

The stock-side static libc was built the way `tools/build-test-libc.sh` specifies: musl 1.2.5 (archive SHA-256 `a9a118bb…c75e4`, matching `source-lock.json`) with `-mfloat-abi=soft`. `boot/handoff/sha256.c` was linked statically with it. The ELF flags are `Version5 EABI, soft-float ABI`, with no `INTERP`. Under `qemu-arm-static`, SHA-256 of the bytes `voyage` matches CPython on the host. This is not a full `Readom.sh`: that still needs the kernel, an initramfs and an AOSP image, which were not packed here.

The official `update.bin` (SHA-256 `80856a11…7a155b`, 247,461,749 bytes, magic `SP01`) does not contain this device's `Linux version`, `3.0.35-lab126`, `Thu Apr 8 09:39:57`, `builder@eink-builds`, `pm_test_show`, or the eips hash. The signature was not stripped, and the stock function bodies were not computed from that public file. The kernel built here is `3.0.35-lab126-voyage-android81+`, not the device's `#2 PREEMPT Thu Apr 8 09:39:57 UTC 2021` (gcc 4.9.1), so its function bodies are not a stand-in for the stock kernel.

## Read-only device report, 2026-11-12

The report is 2195 bytes, SHA-256 `eab14ee928b2abaf6925d1fd2f04e461c1bc0525fef01a6cd5b9252b05864f15`, ending in `VOYAGE_PROBE_DONE`, with `uid=0`. The firmware line is Kindle 5.13.6. `version.txt` was stored as `System Software Version: 038-juno_1306_icewine_wario-373199Thu Apr  8 10:43:14 UTC 2021com.lab126.eink.icewine.os` (newlines were removed by the collector; they are not put back here).

Readings that are complete:

| Field | Value |
|---|---|
| eips | 61104 bytes, `7916bee55c7ec9ab4d2da5859d5b27e3caee77dd971aa93d01fccc8b2fdd6259` |
| uname | `3.0.35-lab126`, `#2 PREEMPT Thu Apr 8 09:39:57 UTC 2021` |
| `/proc/version` | `Linux version 3.0.35-lab126 (builder@eink-builds) (gcc version 4.9.1 (GCC) ) #2 PREEMPT Thu Apr 8 09:39:57 UTC 2021` |
| Hardware | `Freescale i.MX 6SoloLite based Wario Board`, Revision `60000`, CPU part `0xc09` |
| System RAM | `80000000-9fffffff` |
| User FAT | loop mount at `/mnt/base-us`, 3,188,640 KiB total, 71,792 KiB free then |

Those values go into `boot/profiles/voyage-5.13.6.json` on the model branch. This commit only changes the shared gate: `dd_voyage_5_13_6` records the kernel version and `/mnt/base-us`, and `identity_ready` stays 0.

Not filled, and not guessed:

- `log_pos_goal` and `ip` are `[redacted]` in the report. The filtered command line is not the handoff `stock_cmdline`. The PW3 values `log_pos_goal=0x8fff0000` and `ip=off` are not substituted.
- The running kernel's machine id was not read. 4091 from `mach-types` stays under `source` and is not copied into `measured.machine_id`.
- Partition start sectors and the loop byte offset were not read.
- The four `stock_functions` body hashes were not read. The public `update.bin` has no plaintext kernel.
- Wi-Fi calibration paths and `/proc/bootmode` were not read. `/proc/board_id` and the MAC were left out on purpose.

Every `mmcblk0` node's sysfs `ro` is 0. That is the block layer's read-only flag, not how the root filesystem is mounted. The command line says `ro` and `/` is mounted read-only from `/dev/root`. Those are different. The installer writes files on the user FAT only after the identity gate. It does not open `mmcblk0p1` or `mmcblk0boot*`. `ro=0` is not permission to rewrite the stock partitions.

`tools/voyage_profile.py` still requires `installable`, `identity_ready`, `device_confirmed` and every `measured` key. A command line that still contains `[redacted]` fails the build. At run time `CHECK_PROFILE == 3` stops on E105 before the module is loaded and before `install()`. `dd_device_matches` returns before comparing strings.

## Space

The system image is 512 MiB and the data image is 1024 MiB, format 2. While the payload is smaller than the data image, the install peak is still **1600 MiB free**. This report's user store had about 70 MiB free, which is not enough, and the requirement is not lowered to fit. The chip is the 4 GB class. About 3.3 GB on USB is the user store's total, not free space. The 512 MB heap settings were not changed.

## Not done, so this is not a boot

Until the function-body hashes, the complete command line and the runtime machine id are real readings, an installable entry is not packed and the device is not started. A first Android boot would still be a separate step after that, and this round does not authorize it.

## Next read-only collection

`tools/voyage-probe-extra.sh` asks only for the handoff fields that are still empty. Copy it to the Kindle as `/mnt/us/RUNME.sh`, eject, and type `;log runme` in the search box. It writes only `/mnt/us/voyage-probe-extra.txt` and two short lines on the screen. Do not run `Readom.sh`, do not sign in, do not read kernel memory, and do not copy a serial, a MAC or `/proc/board_id`.

`log_pos_goal` is the physical address of the printk buffer, not an identity field. The script prints it only when it is a plain decimal number or `0x` plus at most eight hex digits. `ip` is kept only for `off`, `none`, `on` or `dhcp`. An IP address or any other value is named as withheld and not printed. The raw `/proc/cmdline` line is not written.

No proc file publishes only the numeric machine id. `/proc/atags` also carries the board id and the MAC, so the script does not read it, and it does not write the mach-types number.

The public `update.bin` (`SP01`, certificate number 2, inner `FB03`, target revision `3731990038`, the same number as the archive name and the `373199` in the device's `version.txt`) was not unpacked. KindleTool's extract moves the signature block aside and unpacks without an RSA check, so it was not run. The four function-body hashes are still absent. Do not take them from `/proc/kcore` or from a block device. A stock kernel that is an ordinary file on the root filesystem would be a later read-only question; it is not read in this round.

The commands below are the older list. Most of them are already answered:

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

`pm_test_show`, `l2x0_flush_all`, `l2x0_disable` and `l2x0_inv_all` still have to be hashed from the stock kernel file that matches this uname, not from the PW3 record and not from the Android kernel built here. Until then the handoff module should not be built.
