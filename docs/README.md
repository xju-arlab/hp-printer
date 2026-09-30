# hp-printer 计划主文档

[项目首页](../README.md) · [新对话入口](HANDOFF.md) · [进度记录](progress.md)

> 2026-09-30：追加 C# WPF 图形安装器、窗口内 Authentik 登录和公开状态 API（不是网页）。Pi 保持 Python + uv。RC3 实现与验收边界见 [RC3 记录](verification/windows-rc3-20260930.md)；已有出纸证据属于 RC2。

## 1. 已确认目标

用户已有树莓派控制打印机的可用配置。设备为 **树莓派 4B + USB 连接 HP DeskJet 4900 series**。新建独立 `hp-printer` 项目，解决直接使用打印机网络连接不稳定的问题。

Windows 首选作为系统打印机添加，在 Word、浏览器、PDF 阅读器等应用中直接打印；同时计划支持 CLI 命令提交文件、查看和控制队列。服务端和打印桥为 Python + uv，Windows 安装界面由 C# WPF 实现，无网页前端工程。用户后续明确将 Windows EXE 安装、公网打印和 GitHub/Pi 版本同步提前；LabOS、网页上传和 DOCX 服务端转换仍在后续。

权限已确认：实验室局域网电脑直接打印，管理员登录管理；首版不要求每个打印用户认证。

## 2. 设计结论

- Windows 将任务发送给树莓派的稳定地址，打印机继续用 USB；不再依赖打印机自身 Wi-Fi/IP。
- 已核实 Ubuntu 24.04.4 / arm64 上的 `HP_DeskJet_4900` 队列，使用 CUPS + ipp-usb；P1 备份后保留现有队列及 USB 链路。
- 用户已确认自动排队打印，管理员可暂停、取消和恢复。P1 已从当前 Windows 增加 CUPS 网络入口并验证一项 Windows 作业到达 Pi；稳定 WLAN 地址和其余兼容性还未验收。
- **CUPS 是实际任务排队和设备输出的权威来源**。管理服务只同步状态、执行受限管理操作和接受 API 提交，不建立与 Windows 队列竞争的调度器。
- 优先 IPP/IPPS 系统打印机接入。本次 Windows 使用内置 Microsoft IPP Class Driver，无需 HP 厂商驱动；其他系统/应用和选项仍需分别验收。
- Python + uv 工程已确认，采用根目录 `src/hp_printer/` 包布局。建议 Typer CLI + FastAPI + libcups/pycups + SQLite，systemd 本机部署；不再规划 frontend/backend 双目录。
- CLI 通过管理服务调用同一套提交和控制逻辑，Windows/CLI/API 最终共用 CUPS 队列。CLI 具备可脚本化 JSON 输出、退出码、幂等重试和管理员登录。
- 原型不依赖 LabOS、云服务器、MinIO、Redis 或 SMTP。打印业务稳定后，才提供 LabOS 专用集成接口。

## 3. 子文档索引

| 文档 | 内容 |
|---|---|
| [00 实机基线](00-current-device.md) | 已登录检查的设备、队列、版本、协议异常及检查边界 |
| [01 需求与决策](01-requirements-and-decisions.md) | 已确认条件、范围、默认建议、待回答问题 |
| [02 架构与封装边界](02-architecture.md) | 数据流、CUPS 权威队列、模块、进程、目录 |
| [03 队列、数据与 API](03-queue-and-api.md) | 原生任务接管、状态机、幂等、取消、恢复、接口 |
| [04 Windows 系统打印机](04-windows-integration.md) | IPP 接入策略、脚本设计、驱动与能力验收 |
| [05 部署、诊断与运维](05-deployment-and-operations.md) | 安装/升级/卸载、USB、地址、权限、保留与恢复 |
| [06 分阶段实施与验收](06-roadmap-and-acceptance.md) | P0–P7 小步骤、证据、故障用例 |
| [07 LabOS 对接边界](07-labos-integration.md) | 独立服务与现有 xju-lab 计划的关系 |
| [08 CLI 与 uv 工程](08-cli-and-uv.md) | 命令契约、登录、输出/退出码、Python 包、依赖和部署 |
| [09 Windows 安装与公网](09-windows-release.md) | 本轮优先范围、Authentik、Windows 后台桥、GitHub 与 Pi 同步 |
| [10 状态 API](10-status-api.md) | 设备与 CUPS 状态、缺纸、墨量、缓存和未知值 |
| [本轮实测记录](verification/windows-release-20260929.md) | 实际部署、验收证据和仍待完成项 |
| [资料依据](references.md) | 官方协议依据与本地事实的边界 |
| [交接说明](HANDOFF.md) | 新对话第一步及可复制提示词 |

## 4. 首个成功标准

不先做大而全的管理后台。首先让一台 Windows 在系统中添加树莓派队列，分别从 Word/PDF 打印成功；两台客户端同时提交时，任务进入同一 CUPS 队列；设备离线时能解释任务在哪，不靠删除队列或无限重试解决。

随后把 CLI 文件打印、队列状态、取消、挂起/恢复、设备停用/恢复、故障诊断封装成稳定命令与 API。每一步记录真实证据，用户已有成功配置作为回退基线。

当前必须继续跟踪的检查结果：USB 侧 IPP 响应中 `media-default`、`sides-default` 各一次，CUPS 生产队列响应各两次，严格检查仍失败；本次 Windows 验证与提交成功，但该响应仍不符合 RFC 8011。实测、限制和回退见 [P1 记录](verification/p1-20260929.md)。
