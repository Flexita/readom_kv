# 参与开发

这份文件写给要改代码的人。只想把系统装到 Kindle 上的，看 `docs/install.md`。
安全相关（签名密钥、不写分区的保证、私有数据）在 `SECURITY.md`。
在这里交流和贡献，请遵守 `CODE_OF_CONDUCT.md`。

## 这个项目的几条硬约定

先说清楚，因为它们解释了下面大部分做法：

1. **不写分区、不改引导。** 整套系统是 Kindle 用户区（FAT）上的两个镜像文件，经原厂内核里的
   交接模块跳转进来。卡住时按住电源键不放就回到原厂系统。任何需要写分区的方案都不接受。
2. **设备专属数据不进仓库、不进发行物。** 面板波形、Wi‑Fi 校准与固件、MAC、序列号、ATAG、
   原厂私有内核模块——这些只能在安装时从使用者自己的设备上现场提取。
3. **结论要有实测支撑。** 这个仓库里的文档大量写着"量过多少"。改动如果改变了某个被记下来的
   数值，要么重新量，要么说明为什么不用再量。推断和实测要分开写。
4. **不做临时方案。** 宁可把问题的前提变成编译期或测试期的拒绝，也不要在代码里加特例。

## 构建环境

目前是 Apple Silicon 的 macOS，加上 Lima 虚拟机：ARM64 Ubuntu，里面套一个 x86 chroot，
用来跑 AOSP 8.1 的主机工具。所有步骤都不碰设备。

```bash
python3 tools/fetch-prebuilts.py      # 下载第三方件（EinkBro、WebView、单色 emoji 字体），核对 SHA-256
bash tools/vm.sh start                # 按 config/build-vm.template.yaml 建立并启动虚拟机
bash tools/vm.sh shell                # 进入虚拟机，以下命令在虚拟机里执行
sudo bash /mnt/port/tools/provision-x86-runtime.sh  # AOSP 的 x86 主机工具要的 qemu 和运行库
bash /mnt/port/tools/provision-aosp-chroot.sh
bash /mnt/port/tools/sync-aosp.sh     # 按 source-lock.json 取 AOSP
bash /mnt/port/tools/build-test-libc.sh  # 入口和安装器用的静态 ARM musl；源码包按 source-lock.json 的 test_libc 先放进 /mnt/build-share/toolchains/
bash /mnt/port/tools/build-kernel.sh android-core
PW3_AOSP_INSTALLCLEAN=1 bash /mnt/port/tools/run-aosp-build-job.sh  # 改过包列表时必须带
python3 /mnt/port/tools/export-aosp-images.py --output /mnt/build-share/<导出目录>
```

**系统构建一律经 `tools/run-aosp-build-job.sh`**，不要直接调 `build-aosp-system.sh`：
作业脚本把产出的镜像按内容绑进回执，导出和载荷都认这份回执；绕过它会让导出用上别次构建的回执。
它只从环境变量读选项：

| 变量 | 默认 | 什么时候要给 |
|---|---|---|
| `PW3_AOSP_INSTALLCLEAN` | `0` | 改了 `device/amazon/pw3` 下任何 `.mk` 之后必须是 `1`：不再安装的模块会把文件留在暂存树里，被打进镜像。没带它而 `.mk` 变了，构建会在进 chroot 之前停下 |
| `PW3_BUILD_VARIANT` | `userdebug` | 发行用 `user` |
| `PW3_RELEASE_KEY_DIR` | 无 | `user` 构建必须给，是构建 chroot 里的路径；不能在源码树或共享构建目录之内 |
| `PW3_BUILD_VERSION` | 无 | 发行要给。它成为「设置 > 关于平板电脑 > 版本号」那一行（`ro.build.display.id`），只进 `build.prop`，不影响 `BUILD_ID`、指纹和启动镜像 |
| `PW3_BUILD_DATETIME` | 当前时间 | 要重建某个发行版的 `build.prop` 和指纹时，传它的发行说明里记的值 |

还没做到的：一条命令复现的构建，以及在 Linux 主机上构建。

## 测试

```bash
python3 tools/run-tests.py                       # 宿主机上能跑的那些
# 虚拟机里（能多跑十几项，包括要 AOSP 树和构建产物的）
bash tools/vm.sh shell
cd /mnt/port && python3 tools/run-tests.py
```

套件会把"这里跑不了"的项和它缺什么一起打印出来。**不要靠放宽判据让一项通过**——这个仓库里
已经有过几次"跳过理由写的不是真原因"，办法是把它缺的那样东西做出来。

新加的检查要做**反向验证**：故意把被检查的东西改坏，确认这项真的会失败。只证明"通过"说明不了
检查器还在工作。还有：**树里有、却不在任何人的"要跑什么"清单里的测试，是绿套件上的一个洞**——
`tools/tests/test_every_test_runs.py` 不允许这种情况。

## 补丁系列

对 AOSP 和内核的改动是补丁文件，按序号依次应用（`tools/apply-patch-series.py`）。

这个工具是**只追加**的：它把应用过的补丁和它们的哈希记在源码树的 `.pw3-applied-patches.json`
里，改动一个已经记录过的补丁会被拒绝。要改就把那棵树恢复原状再整套重来：

```bash
git -C <源码树> checkout -- . && git -C <源码树> clean -fdq
```

补丁的正文上方写散文，说明**为什么**这么改、依据是什么。这些文字是这个项目的主要记录形式之一。

## 框架资源的两条规矩

改 `frameworks/base` 的资源覆盖层时：

- **只改值，不加名。** 新增资源名会改变 `R.java`，进而改变启动镜像。
- 覆盖条目上方的注释要**逐字照抄 AOSP 原文**（`aapt2` 会把它抄进 `R.java`）。
- 每次构建之后比对 `/system/framework/arm` 下的 ART 启动文件。变了就意味着装新版会触发
  `/data` 里应用的重新编译，发行说明里必须写明。

## 移植到其他机型

维护者手里只有 PW3，其他机型都要靠有那台机器的人来做。一个仓库装得下多个机型：内核按版本分组，
同一个内核版本共用一套补丁系列；属于一个机型自己的，是一份启动配置（`boot/profiles/<机型>-<固件>.json`）、
一个设备目录（`device/amazon/<机型>/`）和一份内核机型配置（`config/models/<机型>.config`）。
各机型离 PW3 多远、移植要做哪些事，见 `docs/design/porting-to-other-models.md`。动手时开一个"移植"
Issue 记进度；先在自己的 fork 里发布也完全可以。上面四条硬约定对每个机型都一样。

要合回这个仓库，还有四条：

1. **一个机型的 Pull Request 只加这个机型自己的东西**：它的启动配置、设备目录、内核机型配置，再加上
   把这个机型登记进构建脚本的那几行（例如 `tools/build-kernel.sh` 里的机型列表，测试要求它和
   `config/models/` 一一对应）。会改变共用代码行为的改动（`boot/`、`installer/`、`device/amazon/pw3/`、
   共用的补丁系列、构建脚本的其他部分），单独提一个 Pull Request，写清哪些机型需要它、怎么限定只在
   这些机型上生效、其他机型为什么不受影响。合并前，维护者会在构建机上比对改动前后 PW3 的构建产物；
   有不同的，要说明它在 PW3 上为什么也对，并且在 PW3 上验过。
2. **只给模拟器或测试用的代码，按仓库已有的做法隔开。** 内核补丁放 `patches/test-kernel/`，不进发行用的
   补丁系列；启动程序里的测试路径用编译期的构建配置分开。发行构建里不能有这些代码，也不能靠命令行参数
   在发行版里把它们打开。
3. **真机结果要来自这个仓库的构建流程。** 手工重新打包的镜像不算。附上设备自己留下的记录：Kindle 盘上
   `android/logs/` 里这次启动的那个文件夹（里面不含序列号、MAC 地址和 Wi‑Fi 名称，见 `docs/install.md`），
   以及屏幕上看到了什么。只在模拟器里跑过的，写"模拟器"，不写"真机"。
4. **合进来的机型要有一位维护者**：手里有那台机器，审这个机型的文件的改动，每一版发布前在真机上走一遍
   安装和启动并回报。对外分两级：PW3 写"维护者真机验证"，其他机型写"社区维护，由某某在真机上验证"。
   某一版发布前没有收到真机回报的机型，那一版不发它的安装包；连续两版没有回报的，标为"暂无人维护"。

### 合并前要过的几关

一个机型的 Pull Request，以及为它改共用代码的那个 Pull Request，都要依次过下面四关，哪一关没过都不合并。

1. **自动检查**（每个 Pull Request 都跑，`.github/workflows/tests.yml`）：宿主机测试全过（`tools/run-tests.py`）；
   许可证标注齐全（`reuse lint`）；文件里查不出 MAC 地址、序列号、密钥这类私有数据
   （`tools/check-private-data.py`）；除了图片（png、jpg、webp、pgm，内容也得真是图片）不带任何二进制文件，
   内核模块、固件、波形、更新包、越狱包都在此列；动到某个机型自己的文件时，只涉及这一个机型，只动它的文件
   和 `tools/build-kernel.sh` 里登记它的那一行（后两条是 `tools/check-pr-scope.py`）。这些检查防的是疏忽，
   不防故意绕过：Pull Request 改了检查本身，GitHub 跑的就是改过的那一份。文本形式的亚马逊文件和越狱脚本，
   自动检查也认不出来，靠第四关的复审。
2. **PW3 不受影响**：维护者在构建机上分别构建改动前后的 PW3 来比。系统镜像的 ext4 外壳每次构建都不一样，
   所以比的是镜像里逐个文件的内容（两次构建用同一个 `PW3_BUILD_DATETIME`）；入口 `Readom.sh` 里写着系统镜像的
   哈希，要用同一份系统镜像重建再比；内核（`zImage`、模块、`.config`）和其余产物逐字节比。有不同的，要说明
   它在 PW3 上为什么也对，并在 PW3 真机上验过。
3. **真机证据对得上**：除了上面第 3 条要的记录，再附上构建用的提交号、入口目录里的 `build-result.json`
   （记着它要装的 `android/system.img` 的 SHA-256）和 `launcher/build-result.json`（记着 `Readom.sh` 的
   SHA-256），以及在电脑上算出的 Kindle 盘上这两个文件的 SHA-256
   （`shasum -a 256 android/system.img documents/Readom.sh`）。几处对得上，说明盘上装的就是这次构建的产物，
   不是重新打包的镜像；这能查出用错了镜像、混进了重新打包的文件。它查不出有意伪造，也证明不了回执出自哪个
   提交：回执和记录都在贡献者手里，启动记录现在也还对不到具体某一次构建。
4. **书面复审，维护者决定**：维护者给每个这样的 Pull Request 写一份复审，逐条列出问题，每条附文件和行号。
   问题处理完，由维护者决定合不合并。

眼下 PW3 的一些值还写在共用代码里（启动配置的路径、原厂启动文件的哈希、内核版本串等），所以哪怕是和 PW3
同内核的 Voyage、Oasis 1，第一次移植也免不了先提一个改共用代码的 Pull Request，按上面第 1 条单独走。
内核版本不同的机型（Kindle 8，PW4、Oasis 2、Oasis 3、Kindle 10 那一组）还要改交接、存储布局和屏幕驱动的
接口，这些要和那一组第一个动手的人一起设计。

名字里的 `pw3` 是这个平台（i.MX6SL、3.0.35 内核）的名字，不只是一个机型：`gralloc.pw3`、`ro.hardware=pw3`、
`init.pw3*.rc`、`sys.pw3.*` 这些，别的机型照用，不改名。改了，PW3 的构建产物就会变。

合并之后，这个机型在 README 的「其他机型」里写明支持等级和在真机上验证的人；暂无人维护的机型也标在那里，
发行说明照着写。仓库不用 CODEOWNERS：GitHub 只认有写权限的人做代码所有者。改到某个机型的文件时，
维护者会在这个机型的"移植" Issue 里请它的维护者来看。

## 提交

- 提交信息：第一行 `范围: 这次改了什么`，小写开头，不写句号；正文用完整的句子说明
  **为什么**改、依据是什么、验证到哪一步。仓库里已有的提交就是范例。
- 一次提交只做一件事；跨主题的改动分开提。
- Pull Request 按模板写清改了什么、为什么、验证到哪一步。每个 PR 在 GitHub 上会自动跑一遍
  宿主机测试（`.github/workflows/tests.yml`，Linux，带 `--zstd-archive`），再查一遍改动里有没有图片以外的
  二进制文件、机型的 Pull Request 有没有动到别处（`tools/check-pr-scope.py`），没过的不合并。
- 提交前启用一次钩子（每个克隆一次）：

```bash
git config core.hooksPath tools/git-hooks
```

它跑 `tools/check-private-data.py` 检查暂存区。同一个检查也是测试套件里的一项
（`run-tests.py --filter private-data`），因为只在钩子里跑的检查依赖"有人记得启用"，
而这个仓库是要公开的。检查什么、怎么加自己的值，见 `SECURITY.md`。

## 文档

- 中文是主语言，但面向使用者和贡献者的文档每一份都有英文半边：使用者要看的五份
  （`README`、`CHANGELOG`、`docs/install`、`docs/known-issues`、`docs/open-items`）、
  `CONTRIBUTING`、`CODE_OF_CONDUCT`、`SECURITY`、`THIRD_PARTY`、
  `docs/README`，以及 `docs/design/` 下的全部设计记录，
  `tools/tests/test_doc_pairs.py` 守着它们结构一致（今天 18 对）。改了一侧就要改另一侧。
  **目录自己的 README（`boot/`、`device/`、`installer/`、`patches/`、`tools/`）
  只有中文**：它们是给改这一块代码的人看的路标，不在配对表里。
- 文档之间的引用由 `tools/tests/test_doc_links.py` 核对，带目录的 `.md` 路径必须解析得到。
- 哪份文档回答什么问题，见 `docs/README.md`。
