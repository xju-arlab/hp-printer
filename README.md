# hp-printer

树莓派 4B 打印网关：**Python + uv 后端、C# WPF 图形安装器**。以 USB 连接 HP DeskJet 4900 series，向 Windows 提供内网和公网系统打印机入口；完整 CLI 打印和队列管理按后续阶段实现。

> 已完成真实 Authentik 登录、Windows 系统打印机安装和公网 Windows 系统打印：测试作业被 CUPS 报告 completed，用户已确认很快出纸。Word 实际文档打印和真正校外网络仍待验收。

**图形候选版 v0.1.0-rc.6：[GitHub](https://github.com/xju-arlab/hp-printer/releases/tag/v0.1.0-rc.6) · [GitCode](https://gitcode.com/xju-arlab/hp-printer/releases/tag/v0.1.0-rc.6)**。下载运行 `ICTHubPrinterSetup.exe`，登录算法与科研实验室账号并安装，可直接覆盖旧版。RC6 修复重复安装的同名冲突，保留已有队列和打印偏好。账号需已验证邮箱；两端使用同一份 EXE 和 SHA256。重装、升级及图形交互待实机验收，见 [RC6 记录](docs/verification/windows-rc6-20260930.md)。

**公开状态 API：[GET /v1/status](https://hp.icthub.top/v1/status)**，读取设备状态、缺纸和墨量，不提供状态网页。见[接口说明](docs/10-status-api.md)。

```text
Windows Word / PDF → 本机 IPP 桥 → LAN CUPS ─────────────┐
                              → HTTPS + Authentik       v
                                Cloudflare Tunnel → Pi 网关 → CUPS → USB HP
```

**一个物理设备、一条权威 CUPS 队列**。树莓派上的 CUPS/ipp-usb 负责设备侧连接与格式处理；Windows 使用系统自带的 Microsoft IPP Class Driver，无需安装 HP 厂商驱动。hp-printer 只封装队列和管理流程，不另写设备驱动或第二套调度器。

- [计划主索引](docs/README.md)
- [新对话交接与启动提示词](docs/HANDOFF.md)
- [逐步实施与验收](docs/06-roadmap-and-acceptance.md)
- [待确认需求](docs/01-requirements-and-decisions.md)
- [实际进度](docs/progress.md)
- [CLI 与 uv 工程设计](docs/08-cli-and-uv.md)
- [Windows 安装与公网方案](docs/09-windows-release.md)
- [本轮部署与验收记录](docs/verification/windows-release-20260929.md)
- [RC2 真实登录、安装与公网作业](docs/verification/windows-rc2-20260930.md)

项目采用根目录 `pyproject.toml`、`uv.lock` 和 `src/hp_printer/` 布局，不包含前端工程。当前可用 `uv run hp-printer --help`、`--version`、`doctor` 和 `serve --config config.example.toml`。`print`、`jobs` 和管理员队列控制仍按后续阶段实现。

**P1 主链路已验证**：Windows 11 新队列使用系统自带 Microsoft IPP Class Driver（无需 HP 厂商驱动），测试作业由 Pi CUPS 报告完成，用户确认测试页出纸；原有 WSD/USB 队列和默认值保留。严格 IPP 响应中的重复属性尚未修复，稳定地址、Word/PDF 和其他 Windows 兼容仍是收尾项。默认自动排队打印，管理员可暂停、取消和恢复。进展见[实测记录](docs/verification/p1-20260929.md)。

Windows 安装包目标设备名为 **算法实验室·惠普打印机**。RC3 使用 Authentik Flow Executor 在窗口内完成账号密码、动态验证码和授权；使用 PKCE，凭据由当前用户 DPAPI 加密。安全密钥等尚未实现的认证方式会明确提示。内网优先直连指定 Pi，公网通过现有 `hp.icthub.top` HTTP Tunnel，无需客户端 cloudflared。DOCX 上传转换留到后续。见 [RC3 记录](docs/verification/windows-rc3-20260930.md)。

公开仓库：[GitHub](https://github.com/xju-arlab/hp-printer) · [GitCode](https://gitcode.com/xju-arlab/hp-printer)。版本以 GitHub 为准，GitCode 同步 main、标签和候选版发布文件：本地提交推送两端，再用 `bash scripts/sync-pi.sh` 拉取到 Pi；代码部署按版本另行执行。详见 [运维说明](docs/09-windows-release.md)。
