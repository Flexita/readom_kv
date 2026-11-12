# Voyage 首次测试与恢复方案（只写不执行）

**状态：** 提案。未授权清理、部署、安装或首次启动。  
**前提：** 云端已有私有 **USB 离线**实验候选 `VoyageExperimental-offline.sh`（`offline_only=1`，**无**下载 URL；**不是** `Readom.sh`；`device_confirmed=false`）。具备向设备所有者**请求**首次实验授权的云端条件；**不具备**日用/发行/已验证可启动的声明。

## 阶段

### 0. 云端准备（已完成到实验候选）

- experimental voyage-userdebug `system.img`（含 zforce2/fsr/haptics，无 cyttsp 入 system）。
- C `dd_voyage_5_13_6.identity_ready=1`；handoff `PWS_PROFILE=3`。
- `refuse_unless_installable` 在 `experimental_first_test` 下通过（日用仍要 `device_confirmed`）。
- 私有候选：`voyage-experimental-PRIVATE-candidate-*/` + `AUDIT-MANIFEST.json`。
- **停止条件：** 产品 prop 不是 voyage、误产出 `Readom.sh`、或伪造 `device_confirmed` → 销毁该目录，不外发。
- **恢复：** 仅删云端目录；不触碰设备。

### 1. 用户确认清理（未授权，勿执行）

仅提议删除/移走**我们创建或明确无用**的文件，**不动书籍**：

| 候选（须用户点名确认） | 说明 |
|---|---|
| 我们创建的 `fill_disk`（或同等占位） | 约 1600 MiB 量级占位；**仅当用户确认路径与大小** |
| 无用的 `Hotfix.bin`（若存在且用户确认非越狱必需） | 与安装器无关的残留；**误删可能影响越狱恢复** → 必须用户确认 |

**实测空闲：** 探针 `available_1k ≈ 71792`（约 **70 MiB**）。  
**安装峰值（可证公式）：** system 512 + data 1024 + reserve 64 = **1600 MiB**（payload &lt; data 时）。  
**首启 dexopt 额外占用（估计，非实测）：** 另建议预留约 **256 MiB**；合计清出建议 **约 1856 MiB**（**estimate**）。

**停止条件：** 用户未书面确认路径；或清完后 `df` 仍 &lt; 建议值。  
**恢复：** 不做自动删除。

### 2. USB 离线拷贝（未授权；默认路径）

- 入口：`VoyageExperimental-offline.sh`（`offline_only=1`，**不请求外网**）。缺本地载荷 → E303；错误大小 → E302。
- 与入口同目录拷贝：`documents/readom-system-experimental-0.img.zst`（精确文件名与字节数；数据模板已打进入口）。
- Agent Store（本轮）：`/cursor/stores/self/artifacts/voyage-usb-offline-experimental-kit-20261112/`（载荷按 48 MiB 分卷；宿主机 `REASSEMBLE-ON-HOST.sh` 后再拷 Kindle）。
- **不要**改名为 `Readom.sh`。USB 必须拔掉（E104）；写盘前机型匹配（错机 → E101）。
- 空间（本 kit 实测算术）：拷贝前空闲 **≥ ~1607.5 MiB**；两文件已在 documents 后空闲 **≥ ~1450.8 MiB**（含 64 MiB reserve；dexopt 另计）。

### 3. 首次 handoff（未授权）

**停止条件：** bootmode≠main；MACH_TYPE 不符；E101/E104/E105。  
**恢复（无需 Android 已工作）：** 检查失败应回到书库；若已写 `android/` 下镜像，可从电脑删除 `android/system.img` 与 `android/data.img`（**仅 Android 目录**）后点回书库。Voyage 上该路径 **unverified**。

### 4. Android 启动（未授权）

无 host dexpreopt：首启必做 boot.art + 应用编译，512 MiB RAM 下时长/是否 OOM **不可证**。  
**停止条件：** 长时间停在“正在启动 Android”后仍无桌面；或 watchdog 回原厂。  
**恢复：**

- 先等数分钟（dexopt 可能很长）。
- “按住电源约 40 秒回原厂”来自 **PW3/亚马逊通用说明**，在 Voyage 上 **未测**，**不保证不变砖**，不得写成 Voyage 已证实步骤。
- 优先只读核对：USB 出盘、原厂书库仍在、`/proc/bootmode` 仍为 main。
- 若 USB 仍可出盘：从电脑删除 `android/` 下镜像（不动书籍）。

### 5. 回原厂验证（未授权）

确认书库、越狱 `.sh`、书籍完好。  
**停止条件：** 越狱入口丢失 → 按用户所用越狱的**官方**升级后恢复步骤（本仓库不替代）。

## 风险定性

首次测试是 **实验风险**，不是日常可用。Wi‑Fi、Voyage 触控、波形、恢复键时序均 **unverified**。原厂引导未改；不能保证长按 40 秒在 Voyage 上安全。

## 何时才具备“请求首次测试授权”的条件

| 必要条件 | 现状 |
|---|---|
| Staging + 校验报告 | 有 |
| 可执行实验入口（非 Readom.sh）且 fail-closed 到授权点 | **有**（USB offline；device_confirmed=false） |
| C identity + 错机拒绝证据 | **有**（host 测试通过） |
| 本地 USB 载荷（无公网托管） | **有**（Agent Store 分卷 + 宿主机拼接） |
| 用户确认清理项与实测空间（≥~1607.5 MiB 拷贝前） | **未授权** |
| Voyage 上至少一条不依赖“已启动的 Android”的退路 | 文档级有；**硬件未测** |

因此：**可以向用户请求首次实验授权（清空间、USB 拷贝两文件、拔线、点 Experimental），但不能声称已验证可日用或可安全发行。**不需要公开托管或 GitHub Release。**
