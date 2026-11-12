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

## MACH_TYPE (`machine_id`) audit

Consumers in this boot chain:

| Site | Role |
|---|---|
| `native_init` | refuses the module if `__machine_arch_type != TARGET_MACHINE` |
| `transition.S` | loads `PT_MACHINE` into **r1** for the new kernel (ARM boot protocol) |
| `pw_plan_validate` | only checks `machine_id == expected_machine_id` on the plan (both from `TARGET_MACHINE`); does **not** read a machine number from ATAGs |
| `dd_atags` | does **not** write MACH_TYPE; Lab126 ATAGs carry board id / MAC / bootmode |

ATAGs do not carry the ARM `MACH_TYPE`. The bootloader puts it in r1; the stock kernel keeps it as `__machine_arch_type`.

Proven offline (matching Image `bb15c171…76530` + GPL):

- `arch/arm/tools/mach-types`: `mx6sl_wario` = **4091**
- `imx60_wario_defconfig`: only `CONFIG_MACH_MX6SL_WARIO=y`
- Image `machine_desc.nr` = 4091 next to the name pointer for `Freescale i.MX 6SoloLite based Wario Board` (same Hardware string the device reported)

So `profile.machine = 4091` is a **source-proven build pin**, not a `/proc` reading. `measured.machine_id` **must stay null**. Writing 4091 into `measured` is refused by the checker.

## Real first-boot risks (not profile padding)

### bootmode: historical empty read vs 2026-11-12 dedicated probe `main`

| Record | Content |
|---|---|
| `device_probe_extra` (earlier) | `/proc/bootmode` was **empty** (`errors: 1`); kept as recorded; no rewrite, no inferred cause |
| `device_probe_bootmode` (new) | 337 bytes, SHA-256 `eb98afc1…292e`, `uid=0`, `bootmode: main`, `result: ok`, `VOYAGE_PROBE_BOOTMODE_DONE` |
| `measured.bootmode` | `main` (from that dedicated probe) |

`root=/dev/mmcblk0p1` only names the root block device; it is **not** bootmode. Code: `dd_atags` requires a runtime reading of exactly `main`. Gate: `_voyage_bootmode_gate` requires recorded `main` before opening the three flags.

**Filling this gate ≠ installable / bootable.** The three flags stay false; no finished Voyage `system.img`; free-space cleanup and first boot are unauthorized; Wi‑Fi driver path, user-store writes, and recovery remain unverified.

### How a null `measured.machine_id` blocks packaging (honest layering)

- `measured.machine_id` **stays null on purpose**; it is **not** in `MEASURED_KEYS`. Its absence alone does **not** emit `measured.*. is empty`.
- What actually blocks `refuse_unless_installable`: the three flags still false, plus the bootmode=`main` requirement when those flags are opened, plus model/firmware/function checks.
- Runtime second line: `dd_voyage_5_13_6.identity_ready == 0`; `helper.c` stops at install prepare. Flipping JSON alone still fails handoff.

- **Wi-Fi**: modules were not loaded under airplane mode; candidate files ≠ driver path.
- **~70 MiB free on the user store**: install peak stays **1600 MiB**. No automatic deletion; cleanup needs the owner.
- **No finished Voyage Android `system.img` yet**: see below. A PW3 image must not stand in. Compile success ≠ bootable.

## Android image build status (measured on this cloud host)

Scripts assume hostname `lima-pw3` plus a Jammy x86 chroot. This cloud host is x86_64; hostname was set to `lima-pw3` for gates, and an **amd64 Jack** path was added (upstream scripts assume ARM64 lima + QEMU). Nothing is checked out to the Mac.

| Item | Measured |
|---|---|
| Disk / RAM / CPU | ~200 GiB free; 15 GiB RAM; 4 cores — full AOSP runs, slowly |
| AOSP `android-8.1.0_r81` sync | **complete** (~39G, 580 projects) |
| Jammy chroot + python2.7 + Go 1.10.8 | **ready** |
| `cross_compiler.archive_sha256` | original lima archive **not reconstructible** from public git/googlesource; using locked revision `0390252` via revision-matched toolchain (`materialize-cross-compiler-from-git.sh`) |
| Voyage `android-core` kernel | **compiled** `3.0.35-lab126-voyage-android81`; `prepare-kernel-hardware` exported (`device_runtime_verified=false`) |
| `voyage-userdebug` systemimage | **compiling** (experimental/unverified; log `voyage-aosp-system-build.log`) |
| Artifacts | no finished Voyage `system.img` yet; **not bootable**; must not mark installable |

## Gates

`installable` / `identity_ready` / `device_confirmed` stay false. `bootmode=main` is now on record, but a finished Voyage image, owner-confirmed free-space cleanup, and explicit first-boot authorization are still missing. Do not open the three flags for a single field. A PW3 image must not stand in.
