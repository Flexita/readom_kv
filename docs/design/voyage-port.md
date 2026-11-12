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

官方 `update.bin`（SHA-256 `80856a11…7a155b`，247,461,749 字节，文件头 `SP01`）里搜不到这次真机的 `Linux version`、`3.0.35-lab126`、`Thu Apr 8 09:39:57`、`builder@eink-builds`、`pm_test_show` 或 eips 哈希。没有拆签名，也没有从这份公开固件里算出内核函数体。自己编出的 `3.0.35-lab126-voyage-android81+` 不是这台机器上的 `#2 PREEMPT Thu Apr 8 09:39:57 UTC 2021`（gcc 4.9.1），所以不能拿它的函数体冒充原厂内核。

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

不能补、也不猜的：

- `log_pos_goal` 和 `ip` 在报告里是 `[redacted]`。过滤后的命令行不是交接用的 `stock_cmdline`。PW3 的 `log_pos_goal=0x8fff0000` 和 `ip=off` 不拿来填。
- 运行中的机器号没有读到。源码里的 4091 仍只写在 `source`，不写入 `measured.machine_id`。
- 分区起始扇区和 loop 的字节偏移没有读到。
- `stock_functions` 四个函数体哈希没有。公开 `update.bin` 里没有明文内核。
- Wi-Fi 校准文件路径、`/proc/bootmode` 没有读。`/proc/board_id` 和 MAC 故意不采集。

块设备的 sysfs `ro` 全是 0。这是块层的只读标志，不是根文件系统的挂载方式。命令行里的 `ro` 和 `/` 挂在只读的 `/dev/root` 上，是另一件事。安装器只在身份闸门之后写用户 FAT 上的文件，不打开 `mmcblk0p1` 或 `mmcblk0boot*`。`ro=0` 不是去写原厂分区的许可。

`tools/voyage_profile.py` 仍要求 `installable`、`identity_ready`、`device_confirmed` 和全部 `measured` 键。命令行里若留着 `[redacted]`，构建照样退出。运行时 `CHECK_PROFILE == 3` 在加载模块和 `install()` 之前停在 E105。`dd_device_matches` 在字符串比较之前返回。

## 空间

系统镜像 512 MiB，数据镜像 1024 MiB，格式号 2。载荷小于数据镜像时，安装峰值仍是 **1600 MiB 空闲**。这次报告的用户区空闲只有约 70 MiB，不够，门槛不因此降低。芯片是 4 GB 这一档，USB 上大约 3.3 GB 是用户区总量，不是空闲。512 MB 内存上的堆参数没有改。

## 还没做、所以不能说能启动

函数体哈希、完整命令行和运行时机器号到齐之前，不能打包可安装入口，也不能在设备上启动。即便以后到齐，第一次启动 Android 仍是单独的一步，这一轮没有授权。

## 下一次只读采集

`tools/voyage-probe-extra.sh` 只问交接代码还缺的项。把它复制成 Kindle 上的 `/mnt/us/RUNME.sh`，弹出 U 盘，在搜索框输入 `;log runme`。它只写 `/mnt/us/voyage-probe-extra.txt`，并在屏幕上写两行短字。不要运行 `Readom.sh`，不要登录，不要读内核内存，不要抄序列号、MAC 或 `/proc/board_id`。

`log_pos_goal` 是 printk 缓冲的物理地址，不是身份字段。脚本只在它是纯数字或 `0x` 加最多 8 位十六进制时才写出。`ip` 只接受 `off`、`none`、`on`、`dhcp`；IP 地址和其他值只留下“已省略”的说明。原始 `/proc/cmdline` 整行不会写入报告。

运行时机器号没有只含这个数字的 proc 文件。`/proc/atags` 同时带着 board id 和 MAC，脚本不读它，也不把源码里的机器号写进去。

公开 `update.bin`（`SP01`，证书号 2，内层 `FB03`，目标版本号 `3731990038`，与固件包名和真机 `version.txt` 里的 `373199` 一致）没有被拆开。KindleTool 的提取是把签名块挪开再解包，并不做 RSA 校验，所以没有运行。四个函数体哈希仍然没有。不要从 `/proc/kcore` 或块设备里挖内核。若根文件系统上有普通文件形式的原厂内核，那是下一步可以讨论的只读文件，这一轮不读。

下面这段是旧的问题清单，其中大部分这次已经回答：

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

`pm_test_show`、`l2x0_flush_all`、`l2x0_disable`、`l2x0_inv_all` 仍只能从对得上这次 uname 的原厂内核文件计算，不能用 PW3 的哈希，也不能用这里编出的 Android 内核。在此之前交接模块不应被编出来。
