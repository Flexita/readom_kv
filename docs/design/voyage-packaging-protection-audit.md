# Voyage 打包保护审计（独立于镜像编译）

generated_utc: 2026-11-12（云端实验镜像已出之后）

## 结论

完整可执行安装包（`Readom.sh` + 正式 `readom-*.img.zst` + 可点的入口）在设计上被拒绝，直到：

1. JSON 三旗标 `installable` / `identity_ready` / `device_confirmed` 为 true；
2. C 侧 `dd_voyage_5_13_6.identity_ready == 1`（目前为 **0**，字符串全空）；
3. 用户另授权空间清理与首次测试。

本轮只组装 **STAGING-NOT-INSTALLABLE** 候选组件与校验清单，不打开旗标、不产出可误认为正式包的文件名。

## 三旗标如何挡住打包

| 层 | 位置 | 行为 |
|---|---|---|
| JSON | `tools/voyage_profile.problems` / `refuse_unless_installable` | 任一旗标非 true → 拒绝 |
| 调用点 | `boot/build_entry.py`、`boot/build_module.py`、`boot/build_launcher.installer_inputs` | 打包入口直接 `SystemExit` |
| C | `dd_voyage_5_13_6.identity_ready=0`；`helper.c` `install_prepare` | `VOYAGE_INSTALL_BLOCKED` / E105，**即使只改 JSON 也不交接** |
| launcher | `module_profile==3` 时 `build_launcher` 仍只接受 1/2 | 额外硬挡 |

当前 `refuse_unless_installable` 报出的问题恰好是三条旗标（bootmode=main 已满足，不再出现在拒绝列表里）。

## 已证设备身份 vs 未验证启动保护

**已证（只读探针 / 离线解包，不等于 Android 可启动）：**

- eips / uname / cmdline / RAM / 分区起点 / 四函数体 / MACH_TYPE 4091 构建钉 / bootmode=main
- 云端 experimental `voyage-userdebug` system.img 产品属性为 voyage（非 PW3 镜像冒充）

**未验证（保护必须保留）：**

- 真机 Android 启动、Wi‑Fi、Voyage 触控（`zforce2` 在内核 tar 中、未进 system 镜像）、波形固件路径
- 用户区写入 / loop offset 在安装器下的行为
- 恢复路径（含 40 秒电源键：文档来自 **PW3/通用 Kindle 说明**，Voyage **未测**）
- 无 dexpreopt 时首启 dexopt 的时长与峰值内存

## 为何不盲开旗标

打开旗标会让 `build_entry` 开始打可执行入口；在 C `identity_ready`、触控/Wi‑Fi、空间与恢复均未验证时，用户会得到看起来像正式包的危险产物。保留拒绝是正确的 fail-closed。

## PW3 命名继承（不是偷换镜像）

Voyage lunch 继承 `device/amazon/pw3` 板级：`fstab.pw3`、`init.pw3*.rc`。产品 prop 为 `voyage`。这是共享 Wario 板级代码，**不是**把 PW3 `system.img` 当作 Voyage。硬件组件仍带 PW3 波形路径标记，Voyage 上 **unverified**。
