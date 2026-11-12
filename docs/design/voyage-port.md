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

同一天，`tools/apply-patch-series.py` 把 `patches/*.patch` 和 `patches/android-core/*.patch` 共 **85** 个补丁打到这份成员解出的干净树上，**0** 个失败。接着用这份树上的 `imx60_wario_defconfig` 加上 `config/android-core.config` 和一份临时的 Voyage 片段（`LOCALVERSION=-lab126-voyage-android81`、`ARCH_MMAP_RND_BITS=16`、`LAB126_ANDROID_ATH6KL_FIRMWARE=y`）跑 `merge-kconfig.py --check`，**147** 项请求全部生效。

本机 gcc 13.3 编不了这棵 3.0 树（`proc-v7.S` 的 `#`）。改用锁定的 AOSP gcc 4.9：仓库 `https://android.googlesource.com/platform/prebuilts/gcc/linux-x86/arm/arm-linux-androideabi-4.9`，检出 `0390252b6bcc6217966ade31d07f8b12f6f78f89`（`git rev-parse` 与 `source-lock.json` 的 `revision` 一致）。`git archive` 的哈希对不上锁里的 `archive_sha256`：那是一份没有公开 URL 的打包，来源以 git 修订号为准。没有改内核补丁。

用这个编译器、`imx60_wario_defconfig` 和上面的 147 项配置编出了内核。`include/generated/utsrelease.h` 是 `3.0.35-lab126-voyage-android81+`。末尾的 `+` 是因为打过补丁的树相对那次 `git commit` 是脏的，不是发行名。编译命令带 `-msoft-float`。这是编译结果，不是真机启动。

| 产物 | SHA-256 |
|---|---|
| `zImage` | `bfc22d8738da550af66e378618083eaf7e24e579962dc4e6511c13fd42a1b735` |
| `uImage` | `8fe014996a74ae8215fa0dbe20992175a5d154054baa62e75f4d2e41a068e89d` |

uImage 头里的加载地址是 `0x80008000`。这是这次编译写进头里的数。同一天的真机 `/proc/iomem` 只有一行 System RAM：`80000000-9fffffff`，512 MiB，起点与 `MX6SL_PHYS_OFFSET` 一致。这个范围可以写入 `measured.ram`。它和 PW3 记录相同，是因为设备这样报，不是为了制造一个假的差异。

原厂侧静态程序按 `tools/build-test-libc.sh` 的办法编了 musl 1.2.5（归档 SHA-256 `a9a118bb…c75e4`，与 `source-lock.json` 一致），`-mfloat-abi=soft`。用它静态链接了 `boot/handoff/sha256.c`。ELF 头标志是 `Version5 EABI, soft-float ABI`，没有 `INTERP`。`qemu-arm-static` 对输入 `voyage` 算出的 SHA-256 与主机 Python 相同。这不是完整的 `Readom.sh`：完整入口还要内核、initramfs 和 AOSP 镜像，那些没有在这里打包。

对封装后的 `update.bin` 直接搜明文找不到真机横幅；解包后的 `uImage`/`Image` 才带有一致的 `#2 PREEMPT Thu Apr 8 09:39:57 UTC 2021`（见下一节）。自己编出的 `3.0.35-lab126-voyage-android81+` 不是那份原厂内核，不能拿它的函数体冒充。

## 2026-11-12 的只读真机报告

报告 2195 字节，SHA-256 `eab14ee928b2abaf6925d1fd2f04e461c1bc0525fef01a6cd5b9252b05864f15`，末行 `VOYAGE_PROBE_DONE`，`uid=0`。固件显示 Kindle 5.13.6。`version.txt` 原文是 `System Software Version: 038-juno_1306_icewine_wario-373199Thu Apr  8 10:43:14 UTC 2021com.lab126.eink.icewine.os`（采集时去掉了换行，这里不补空格）。

已经可以如实记下的：

| 项 | 读数 |
|---|---|
| eips | 61104 字节，`7916bee55c7ec9ab4d2da5859d5b27e3caee77dd971aa93d01fccc8b2fdd6259` |
| uname | `3.0.35-lab126`，`#2 PREEMPT Thu Apr 8 09:39:57 UTC 2021` |
| `/proc/version` | `Linux version 3.0.35-lab126 (builder@eink-builds) (gcc version 4.9.1 (GCC) ) #2 PREEMPT Thu Apr 8 09:39:57 UTC 2021` |
| Hardware | `Freescale i.MX 6SoloLite based Wario Board`，Revision `60000`，CPU part `0xc09` |
| System RAM | `80000000-9fffffff` |
| 用户 FAT | `/mnt/base-us` 上的 loop，总 3,188,640 KiB，当时空闲 71,792 KiB |

这些数写进机型分支的 `boot/profiles/voyage-5.13.6.json`。本提交只改共用闸门：`dd_voyage_5_13_6` 记下内核版本和 `/mnt/base-us`，`identity_ready` 仍是 0。

## 补充探针与离线内核（机型分支写入）

补充报告 1779 字节，SHA-256 `47a04517…a4ed`，`result: partial`，`errors: 1`。允许名单内的 cmdline（含 `log_pos_goal=0x8fff0000`、`ip=off`）、p1–p4 的 start、loop offset 8192 已写入机型分支的 `measured`。本分支的 `measured` 仍全是 null，共用闸门继续 fail-closed。

`/proc/bootmode` 读出来是空字符串——这就是那一个 error，**不能**填成 `main`。`machine_id` 仍是 `not collected`，不能变成数值；源码里的 4091 只留在 `source`。

Wi-Fi：飞行模式下模块未加载；`/opt/ar6k/...` 下候选普通文件存在且有大小，不等于确定的驱动路径。

公开 `update.bin` 已用 KindleTool 做格式解包（下载 SHA-256 ≠ RSA 验签；未改签名；未运行解出代码）。`imx60_wario/uImage` → zImage → Image（`bb15c171…76530`）带有与真机一致的 `#2 PREEMPT Thu Apr 8 09:39:57 UTC 2021` 横幅，四个 `stock_functions` 哈希已写入机型分支。公开固件已给出匹配内核，因此不另产根文件系统内核文件探测脚本。不读 `/proc/kcore`、`/dev/mem` 或引导分区。

块设备的 sysfs `ro` 全是 0。这是块层的只读标志，不是根文件系统的挂载方式。命令行里的 `ro` 和 `/` 挂在只读的 `/dev/root` 上，是另一件事。安装器只在身份闸门之后写用户 FAT 上的文件，不打开 `mmcblk0p1` 或 `mmcblk0boot*`。`ro=0` 不是去写原厂分区的许可。

`tools/voyage_profile.py` 仍要求 `installable`、`identity_ready`、`device_confirmed` 和全部 `measured` 键。命令行里若留着 `[redacted]`，构建照样退出。运行时 `CHECK_PROFILE == 3` 在加载模块和 `install()` 之前停在 E105。`dd_device_matches` 在字符串比较之前返回。

## 空间

系统镜像 512 MiB，数据镜像 1024 MiB，格式号 2。载荷小于数据镜像时，安装峰值仍是 **1600 MiB 空闲**。这次报告的用户区空闲只有约 70 MiB，不够，门槛不因此降低。芯片是 4 GB 这一档，USB 上大约 3.3 GB 是用户区总量，不是空闲。512 MB 内存上的堆参数没有改。

## MACH_TYPE 与首次启动风险

`MACH_TYPE` **4091** 是离线可证的构建钉（匹配 Image 的 `machine_desc.nr` + GPL），不是 `/proc` 实测；`measured.machine_id` 保持 null。交接里它进 `TARGET_MACHINE` / transition **r1**；ATAG 不携带该数字。

真实阻塞在别处：`dd_atags` 要求 `/proc/bootmode == main`（上次读到空串）；用户区空闲远低于 1600 MiB（不自动删书）；尚无 Voyage Android `system.img`。`tools/voyage-probe-bootmode.sh` 只再读 bootmode。`identity_ready` / `device_confirmed` / `installable` 仍为 false。
