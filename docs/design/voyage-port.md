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

uImage 头里的加载地址是 `0x80008000`。这是这次编译写进头里的数，来自该 defconfig 的 `MX6SL_PHYS_OFFSET`，不是从 PW3 配置抄来的，也还不是设备上 `/proc/iomem` 的读数，所以仍然不放进 `measured.ram`。

原厂侧静态程序按 `tools/build-test-libc.sh` 的办法编了 musl 1.2.5（归档 SHA-256 `a9a118bb…c75e4`，与 `source-lock.json` 一致），`-mfloat-abi=soft`。用它静态链接了 `boot/handoff/sha256.c`。ELF 头标志是 `Version5 EABI, soft-float ABI`，没有 `INTERP`。`qemu-arm-static` 对输入 `voyage` 算出的 SHA-256 与主机 Python 相同。这不是完整的 `Readom.sh`：完整入口还要内核、initramfs 和 AOSP 镜像，那些没有在这里打包。

官方 `update.bin` 里没有 squashfs 魔数，也没有明文的 `Linux version` 或 `eips`。偏移 30755 处的 `1f 8b` 不是 gzip。因此没有从固件里取出 uname、eips 哈希或分区表。没有去拆签名或写分区。

## 没有、所以拒绝安装的

`measured` 里这些键都是 null：`eips_sha256`、`eips_bytes`、`uname_release`、`uname_version`、`machine_id`、`stock_cmdline`、`ram`、`partition_table`、`stock_functions`。

校验器拒绝的是 PW3 上量到的那几样：eips 哈希、`uname -v` 构建戳、命令行、内核函数体。Voyage 的 `mach-types` 自己写着 4091，defconfig 自己写着 `CONFIG_LOCALVERSION="-lab126"`，所以机器号 4091 和发行串 `3.0.35-lab126` 如果真机读数相同，不算抄袭，校验器放行。内存布局即使碰巧相同也不拒绝，以免逼人编一个假的差异；但现在 `measured.ram` 仍是空的，因为源码里两个物理基址对不上。

`tools/voyage_profile.py` 在 `boot/build_entry.py`、`boot/build_launcher.py`（带安装器）和 `boot/build_module.py` 里被调用。缺任何一项，或者 Voyage 的测量值等于 Paperwhite 3 的 eips、uname、命令行或内核函数体记录，构建直接退出。运行时 `CHECK_PROFILE == 3` 在加载模块和 `install()` 之前写日志并停在 E105。`dd_voyage_5_13_6.identity_ready` 为 0，`dd_device_matches` 在做字符串比较之前返回。

## 空间（估计）

系统镜像保持 512 MiB。数据镜像改为 1024 MiB，格式号 2。加上 64 MiB 余量，安装要求 **1600 MiB 空闲**。依据和“没在 Voyage 上量过”写在 `device/amazon/pw3/BoardConfig.mk`。512 MB 内存上的堆参数没有改：那些数是在同系列芯片的 PW3 上量的，改了却没新的测量就不算优化。

## 真机上要只读采集的

不要运行 `Readom.sh`，不要登录。在 Kindle 上执行 `tools/voyage-readonly-probe.sh`（只读，打印到标准输出）。脚本会删掉 Serial 行、MAC 形状的字符串和 12 位十六进制编号。不要把 `/proc/board_id` 或 Wi-Fi 名加进去。下面这段和脚本问的是同一组事：

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

内核函数体哈希（`pm_test_show`、`l2x0_flush_all`、`l2x0_disable`、`l2x0_inv_all`）要等上面的 `uname` 对上某一份官方内核镜像之后，从那份镜像而不是从 PW3 记录里算。在此之前交接模块不应被编出来。
