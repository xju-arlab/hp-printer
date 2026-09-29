# hp-printer

树莓派 4B 打印网关：**纯 Python 后端，使用 uv 管理项目，提供 CLI 打印和队列管理命令**。以 USB 连接 HP DeskJet 4900 series，向局域网 Windows 提供系统打印机入口。

> 当前项目文档阶段：P1 已打通 Windows → Pi CUPS → ipp-usb → USB 的系统打印主链路，且用户确认测试页出纸。CUPS IPP 重复属性仍是已知协议缺陷；稳定地址及其他兼容项待收尾。Python 服务、uv 工程和 CLI 尚未实现。

```text
Windows Word / PDF ── IPP/IPPS ──┐
                               v
                         树莓派 4B / CUPS ── USB ── HP DeskJet 4900
                               ^
hp-printer CLI / 后续 LabOS ── API ┘
```

**一个物理设备、一条权威 CUPS 队列**。树莓派上的 CUPS/ipp-usb 负责设备侧连接与格式处理；Windows 使用系统自带的 Microsoft IPP Class Driver，无需安装 HP 厂商驱动。hp-printer 只封装队列和管理流程，不另写设备驱动或第二套调度器。

- [计划主索引](docs/README.md)
- [新对话交接与启动提示词](docs/HANDOFF.md)
- [逐步实施与验收](docs/06-roadmap-and-acceptance.md)
- [待确认需求](docs/01-requirements-and-decisions.md)
- [实际进度](docs/progress.md)
- [CLI 与 uv 工程设计](docs/08-cli-and-uv.md)

项目采用根目录 `pyproject.toml`、`uv.lock` 和 `src/hp_printer/` 布局，不包含前端工程。拟提供 `uv run hp-printer print 文件.pdf`、`jobs list`、`jobs cancel`、`printer pause/resume` 等命令；当前为设计约定，尚未实现。

**P1 主链路已验证**：Windows 11 新队列使用系统自带 Microsoft IPP Class Driver（无需 HP 厂商驱动），测试作业由 Pi CUPS 报告完成，用户确认测试页出纸；原有 WSD/USB 队列和默认值保留。严格 IPP 响应中的重复属性尚未修复，稳定地址、Word/PDF 和其他 Windows 兼容仍是收尾项。默认自动排队打印，管理员可暂停、取消和恢复。进展见[实测记录](docs/verification/p1-20260929.md)。

P1 现场变更有受限备份和回退步骤；P2 将从 Python + uv 的只读核心与 CLI 开始，不开发前端。用户需要现场确认测试页是否完整出纸。
