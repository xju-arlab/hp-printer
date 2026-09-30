# hp-printer

树莓派 4B 打印网关：**纯 Python 后端，使用 uv 管理项目，提供 CLI 打印和队列管理命令**。以 USB 连接 HP DeskJet 4900 series，向局域网 Windows 提供系统打印机入口。

> 已完成真实 Authentik 登录、Windows 系统打印机安装和公网 Windows 系统打印：测试作业被 CUPS 报告 completed。新测试纸目视确认、Word 实际文档打印和真正校外网络仍待验收。

**[下载私有候选版 v0.1.0-rc.2](https://github.com/xju-arlab/hp-printer/releases/tag/v0.1.0-rc.2)**：EXE 与 SHA256，需有仓库访问权限。请使用 RC2，修复了 RC1 的登录验证和 Windows 接入问题。

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

Windows 安装包目标设备名为 **算法实验室·惠普打印机**。安装时通过浏览器登录 ICTHub，需已验证邮箱及打印授权组；凭据使用当前用户 DPAPI 加密。内网优先直连指定 Pi，公网通过现有 `hp.icthub.top` HTTP Tunnel，无需客户端 cloudflared。DOCX 上传转换留到后续。

版本以私有仓库 [xju-arlab/hp-printer](https://github.com/xju-arlab/hp-printer) 为准：本地提交推送，再用 `bash scripts/sync-pi.sh` 拉取到 Pi，最后执行部署脚本。详见 [运维说明](docs/09-windows-release.md)。
