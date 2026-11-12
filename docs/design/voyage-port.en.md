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

A raw search of the wrapped `update.bin` does not find the device banner; the unpacked `uImage`/`Image` does carry the matching `#2 PREEMPT Thu Apr 8 09:39:57 UTC 2021` (see the next section). The kernel built here is `3.0.35-lab126-voyage-android81+`, not that stock image, so its function bodies are not a stand-in.

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

## Extra probe and offline kernel (written on the model branch)

The extra report is 1779 bytes, SHA-256 `47a04517…a4ed`, `result: partial`, `errors: 1`. The allow-listed cmdline (including `log_pos_goal=0x8fff0000` and `ip=off`), p1–p4 starts, and loop offset 8192 are written into `measured` on the model branch. This branch keeps every `measured` key null so the shared gate stays fail-closed.

`/proc/bootmode` read as an empty string — that is the one error and must **not** be filled as `main`. `machine_id` stays `not collected` and must not become a number; source `4091` stays under `source` only.

Wi-Fi: modules were not loaded under airplane mode. Candidate ordinary files under `/opt/ar6k/...` exist with sizes; that is not a confirmed runtime driver path.

The public `update.bin` was unpacked with KindleTool as a format parse (download SHA-256 ≠ RSA verification; signatures not altered; extracted code not executed). `imx60_wario/uImage` → zImage → Image (`bb15c171…76530`) carries the exact device banner `#2 PREEMPT Thu Apr 8 09:39:57 UTC 2021`, and the four `stock_functions` hashes are on the model branch. Because the public firmware already yielded a matching kernel, no rootfs kernel-file probe script is produced. `/proc/kcore`, `/dev/mem` and boot partitions are not read.

Every `mmcblk0` node's sysfs `ro` is 0. That is the block layer's read-only flag, not how the root filesystem is mounted. The command line says `ro` and `/` is mounted read-only from `/dev/root`. Those are different. The installer writes files on the user FAT only after the identity gate. It does not open `mmcblk0p1` or `mmcblk0boot*`. `ro=0` is not permission to rewrite the stock partitions.

`tools/voyage_profile.py` still requires `installable`, `identity_ready`, `device_confirmed` and every `measured` key. A command line that still contains `[redacted]` fails the build. At run time `CHECK_PROFILE == 3` stops on E105 before the module is loaded and before `install()`. `dd_device_matches` returns before comparing strings.

## Space

The system image is 512 MiB and the data image is 1024 MiB, format 2. While the payload is smaller than the data image, the install peak is still **1600 MiB free**. This report's user store had about 70 MiB free, which is not enough, and the requirement is not lowered to fit. The chip is the 4 GB class. About 3.3 GB on USB is the user store's total, not free space. The 512 MB heap settings were not changed.

## Not done, so this is not a boot

The model branch still lacks a runtime `machine_id`; `identity_ready` / `device_confirmed` / `installable` stay false. Until those open on evidence, an installable entry is not packed and the device is not started. A first Android boot would still be a separate step after that, and this round does not authorize it.

No ordinary proc file publishes only the machine id. `/proc/atags` also carries the board id and MAC, so it is not read. Expanding collection into boot partitions or memory needs a separate necessity-and-risk note first; it is not done here.
