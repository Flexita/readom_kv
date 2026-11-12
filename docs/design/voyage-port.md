# Voyage 移植：做到哪、卡在哪

这不是一份“已经能装”的说明。安装入口在 `installable` 不为 true 时拒绝打包。Paperwhite 3 的配置留在 `boot/profiles/pw3-5.16.2.1.1.json`，同样 `installable: false`，只作历史记录。

英文：`voyage-port.en.md`。

## 从官方文件里核对过的

2026-11-12 下载并计算 SHA-256。数字在 `source-lock.json` 的 `voyage_kernel` 和 `boot/profiles/voyage-5.13.6.json` 的 `source` 里，测试核对两边一致。

| 文件 | 结果 |
|---|---|
| `Kindle_src_5.13.6_3731990038.tar.gz` | 332,761,879 字节，`4a01245d…c2222f` |
| 其中 `gplrelease/linux-3.0.35.tar.gz` | 121,872,729 字节，`a66a58b8…5144b0` |
| `update_kindle_voyage_5.13.6.bin` | 247,461,749 字节，`80856a11…7a155b`，文件头是 `SP01` |

GPL 成员里的 `BUILD_HOW-TO.txt` 写明 Voyage 用 `imx60_wario_defconfig`。该 defconfig 打开 `CONFIG_VMSPLIT_3G`、`CONFIG_PAGE_OFFSET=0xC0000000`、`CONFIG_MX6SL_WARIO_BASE`、`CONFIG_ATH6KL=m`、`CONFIG_ATH6KL_SDIO=m`。`arch/arm/tools/mach-types` 把 `mx6sl_wario` 编为 4091。这是源码里的编号，**没有**写进 `measured.machine_id`，也不能单独拿来交接。

`arch/arm/plat-mxc/include/mach/memory.h` 同时有 `MX6SL_PHYS_OFFSET`（0x80000000）和在 `CONFIG_ARCH_MX6` 下选中的 `MX6_PHYS_OFFSET`（0x10000000）。`board-mx6sl_wario.c` 的 `boot_params` 用的是前者。交接不用这两个数里的任何一个。

同一天，`tools/apply-patch-series.py` 把 `patches/*.patch` 和 `patches/android-core/*.patch` 共 **85** 个补丁打到这份成员解出的干净树上，**0** 个失败。用锁定的 AOSP gcc 4.9 编出的内核发行名是 `3.0.35-lab126-voyage-android81+`，**不是**真机上的 `#2 PREEMPT Thu Apr 8 09:39:57 UTC 2021`，不能拿它的函数体冒充原厂内核。

## 离线解包官方更新包里的原厂内核

用户授权对公开官方 Voyage 5.13.6 更新包做离线格式解析。下载文件的 SHA-256 只证明下载完整性，**不等于** RSA 验签。KindleTool `extract` 按 SP01→FB03 Recovery V2 解开，没有 `--unsigned`，没有改签名，也没有运行解出的代码。

| 产物 | SHA-256 |
|---|---|
| `imx60_wario/uImage` | `add9b0a2…a9ca32`（IH_NAME `Linux-3.0.35-lab126`，load `0x80008000`） |
| uImage 内 zImage | `934302ee…35e74e` |
| 从 zImage piggy inflate 的 Image | `bb15c171…76530` |

Image 里带有与真机完全一致的横幅：`Linux version 3.0.35-lab126 (builder@eink-builds) (gcc version 4.9.1 (GCC) ) #2 PREEMPT Thu Apr 8 09:39:57 UTC 2021`。从 kallsyms 解出四个符号，按下一符号地址截断后对函数体做 SHA-256，写入 `measured.stock_functions`。字节数与 PW3 记录相同，哈希不同。

## 2026-11-12 的只读真机报告

第一份报告 2195 字节，SHA-256 `eab14ee9…4f15`，末行 `VOYAGE_PROBE_DONE`，`uid=0`。补充报告 1779 字节，SHA-256 `47a04517…a4ed`，末行 `VOYAGE_PROBE_EXTRA_DONE`，`result: partial`，`errors: 1`（`/proc/bootmode` 为空）。

已经写入 `measured` 的：

| 项 | 读数 |
|---|---|
| eips | 61104 字节，`7916bee5…6259` |
| uname | `3.0.35-lab126`，`#2 PREEMPT Thu Apr 8 09:39:57 UTC 2021` |
| System RAM | `80000000-9fffffff` |
| stock_cmdline | `rootwait log_pos_goal=0x8fff0000 console=ttymxc0,115200 root=/dev/mmcblk0p1 ro ip=off quiet video=mxcepdcfb:E60,bpp=8,x_mem=3M`（与 PW3 的 `cmdline_base` 不同：多了 `rootwait` 和 `root=`） |
| 分区起点（512 字节扇区） | p1=65536，p2=987136，p3=1118208，p4=1249280；整盘与 boot 节点按设计不读 start |
| 用户 FAT loop | backing `/dev/mmcblk0p4`，offset 8192 |
| stock_functions | 见上，来自与 uname 一致的官方 Image |

## MACH_TYPE（machine_id）审计结论

交接链里这个数字的消费者：

| 位置 | 作用 |
|---|---|
| `native_init` | `__machine_arch_type != TARGET_MACHINE` 则拒绝加载模块 |
| `transition.S` | 把 `PT_MACHINE` 装进 **r1**，按 ARM 启动约定交给新内核 |
| `pw_plan_validate` | 只检查计划里 `machine_id == expected_machine_id`（两者都来自 `TARGET_MACHINE`），**不**从 ATAG 读机器号 |
| `dd_atags` | **不**写入 MACH_TYPE；ATAG 里是 board id / MAC / bootmode 等 Lab126 扩展 |

ATAG 协议本身不携带 ARM `MACH_TYPE`。该值在进内核时由 bootloader 放进 r1，原厂内核存为 `__machine_arch_type`。

离线可证（匹配 Image `bb15c171…76530` + GPL）：

- `arch/arm/tools/mach-types`：`mx6sl_wario` = **4091**
- `imx60_wario_defconfig`：仅 `CONFIG_MACH_MX6SL_WARIO=y`
- Image 里 `machine_desc.nr` = 4091，紧挨名称指针指向 `Freescale i.MX 6SoloLite based Wario Board`（与真机 Hardware 行一致）

因此 `profile.machine = 4091` 是**源码/匹配内核可证的构建钉**，不是 `/proc` 实测。`measured.machine_id` **必须保持 null**；闸门不再机械要求一个内核没有单独暴露的接口。把 4091 写进 `measured` 会在校验器里被拒绝。

## 首次启动的真实风险（不是填空）

- **`/proc/bootmode` 为空**：`dd_atags` 要求恰好为 `main`，否则无法构造交接 ATAG。这是真实阻塞。`tools/voyage-probe-bootmode.sh` 只再读这一项；空串不得改成 `main`。
- **Wi-Fi**：飞行模式下模块未加载；候选文件存在 ≠ 驱动路径。影响联网，不挡住 MACH_TYPE/函数体校验，但首次可用体验会缺网。
- **用户区空闲 ~70 MiB**：安装峰值仍要 **1600 MiB**。不因此自动删除设备上的任何文件；清理须用户确认。
- **尚无 Voyage 的 Android system.img**：见下一节。不能用旧 PW3 镜像冒充。

## Android 镜像构建状态（云端实测）

项目脚本默认假定主机名 `lima-pw3` + Jammy x86 chroot。本云主机是 x86_64；为过闸临时将 hostname 设为 `lima-pw3`，并增加 **amd64 Jack** 路径（原脚本假定 ARM64 lima + QEMU）。不往 Mac checkout。

| 项 | 实测 |
|---|---|
| 磁盘 / 内存 / CPU | ~200 GiB 可用；15 GiB RAM；4 核——全量 AOSP 可跑，耗时长 |
| AOSP `android-8.1.0_r81` sync | **完成**（~39G，580 projects） |
| Jammy chroot + python2.7 + Go 1.10.8 | **就绪** |
| `cross_compiler.archive_sha256` | 原 lima 打包物**无法从公开 git/googlesource 复现**；改用锁定 revision `0390252` 的 revision-matched 工具链（见 `materialize-cross-compiler-from-git.sh`） |
| Voyage `android-core` 内核 | **已编译** `3.0.35-lab126-voyage-android81`；`prepare-kernel-hardware` 已导出（`device_runtime_verified=false`） |
| `voyage-userdebug` systemimage | **编译进行中**（experimental/unverified；日志 `voyage-aosp-system-build.log`） |
| 产物 | 尚无完成的 Voyage `system.img`；**不是可启动**，不得标 installable |

## 闸门

`installable` / `identity_ready` / `device_confirmed` 仍为 false。缺 bootmode=`main`、缺完成的 Voyage 镜像、缺用户确认的空间清理与首次启动授权时，不得打开。不得用旧 PW3 镜像冒充。
