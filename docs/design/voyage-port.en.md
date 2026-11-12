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

The same day, `tools/apply-patch-series.py` applied all **85** patches under `patches/*.patch` and `patches/android-core/*.patch` to a fresh tree of this member, with **0** failures. The kernel built with the pinned AOSP gcc 4.9 is named `3.0.35-lab126-voyage-android81+`. That is **not** the device's `#2 PREEMPT Thu Apr 8 09:39:57 UTC 2021`, so its function bodies are not a stand-in for the stock kernel.

## Offline unpack of the official update package

Authorized offline format parsing of the public official Voyage 5.13.6 update package. The download SHA-256 is integrity of the downloaded file, **not** an RSA signature check. KindleTool `extract` unpacks SP01→FB03 Recovery V2 without `--unsigned`, without altering signatures, and without running extracted code.

| Artifact | SHA-256 |
|---|---|
| `imx60_wario/uImage` | `add9b0a2…a9ca32` (IH_NAME `Linux-3.0.35-lab126`, load `0x80008000`) |
| zImage inside the uImage | `934302ee…35e74e` |
| Image inflated from the zImage piggy | `bb15c171…76530` |

The Image contains the exact device banner: `Linux version 3.0.35-lab126 (builder@eink-builds) (gcc version 4.9.1 (GCC) ) #2 PREEMPT Thu Apr 8 09:39:57 UTC 2021`. The four symbols were recovered from kallsyms; each body is SHA-256 from the symbol through the next kallsyms address, and written into `measured.stock_functions`. The sizes match the PW3 record; the digests do not.

## Read-only device reports on 2026-11-12

The first report is 2195 bytes, SHA-256 `eab14ee9…4f15`, ending `VOYAGE_PROBE_DONE`, `uid=0`. The extra report is 1779 bytes, SHA-256 `47a04517…a4ed`, ending `VOYAGE_PROBE_EXTRA_DONE`, `result: partial`, `errors: 1` (empty `/proc/bootmode`).

Already written into `measured`:

| Item | Reading |
|---|---|
| eips | 61104 bytes, `7916bee5…6259` |
| uname | `3.0.35-lab126`, `#2 PREEMPT Thu Apr 8 09:39:57 UTC 2021` |
| System RAM | `80000000-9fffffff` |
| stock_cmdline | `rootwait log_pos_goal=0x8fff0000 console=ttymxc0,115200 root=/dev/mmcblk0p1 ro ip=off quiet video=mxcepdcfb:E60,bpp=8,x_mem=3M` (differs from the PW3 `cmdline_base`: adds `rootwait` and `root=`) |
| partition starts (512-byte sectors) | p1=65536, p2=987136, p3=1118208, p4=1249280; whole disk and boot nodes have no start by design |
| user FAT loop | backing `/dev/mmcblk0p4`, offset 8192 |
| stock_functions | as above, from the official Image that matches this uname |

Not filled, and not guessed:

- `measured.machine_id` stays null. No ordinary proc file publishes only that number; `/proc/atags` also carries the board id and MAC, so it is not read. Source `4091` stays under `source` only.
- `/proc/bootmode` read as an empty string. That is the extra report's only error and is **not** written as `main`.
- Wi-Fi: under airplane mode, `ar6000` / `ath6kl*` were not loaded. Candidate ordinary files under `/opt/ar6k/...` exist with sizes; that is **not** a confirmed runtime driver path.
- No reads of `/proc/kcore`, `/dev/mem`, boot partitions, or block devices opened to dig out a kernel. The public firmware already yielded a matching kernel, so no rootfs kernel-file probe script is produced.

`tools/voyage_profile.py` still requires `installable`, `identity_ready`, `device_confirmed` and every `measured` key. A missing `machine_id` still exits the build. At runtime `CHECK_PROFILE == 3` stops at E105 before the module load and `install()`.

## Space

System image 512 MiB, data image 1024 MiB, format 2. Install peak free space stays **1600 MiB**. This report's user area had only about 70 MiB free; the floor is not lowered.

## Still missing before a first boot claim

Until a runtime machine id is collected and `identity_ready` / `device_confirmed` / `installable` are opened on evidence, an installable entry is not packed and the device is not started. A first Android boot would still be a separate step after that, and this round does not authorize it.

Any expansion into boot partitions or memory needs a separate necessity-and-risk note first; it is not done in this round.
