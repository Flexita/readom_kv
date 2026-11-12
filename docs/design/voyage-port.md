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

不能补、也不猜的：

- `measured.machine_id` 仍是 null。没有只发布该数字的普通 proc 文件；`/proc/atags` 还带着 board id 和 MAC，不读。源码里的 4091 只留在 `source`。
- `/proc/bootmode` 读出来是空字符串。这是补充报告里唯一的 error，**不能**写成 `main`。
- Wi-Fi：飞行模式下 `ar6000` / `ath6kl*` 未加载。`/opt/ar6k/...` 下有候选普通文件及大小，**不等于**已确认的运行时驱动路径。
- 不读 `/proc/kcore`、`/dev/mem`、引导分区或任意为取内核而打开的块设备。公开固件已给出匹配内核，因此不再产出根文件系统内核文件探测脚本。

`tools/voyage_profile.py` 仍要求 `installable`、`identity_ready`、`device_confirmed` 和全部 `measured` 键。缺 `machine_id` 时构建照样退出。运行时 `CHECK_PROFILE == 3` 在加载模块和 `install()` 之前停在 E105。

## 空间

系统镜像 512 MiB，数据镜像 1024 MiB，格式号 2。安装峰值仍是 **1600 MiB 空闲**。这次报告的用户区空闲只有约 70 MiB，不够，门槛不因此降低。

## 还没做、所以不能说能启动

运行时机器号到齐、并把 `identity_ready` / `device_confirmed` / `installable` 按证据打开之前，不能打包可安装入口，也不能在设备上启动。即便以后到齐，第一次启动 Android 仍是单独的一步，这一轮没有授权。

若要把采集扩大到引导分区或内存：先单独说明必要性与风险，这一轮不执行。
