# 资料依据与证据边界

[返回主计划](README.md)

核对日期：2026-09-29。以下为官方项目或厂商资料；设计中的限制值、目录和阶段划分是本项目建议，不是官方保证。部署时以实际安装版本能力为准。

| 来源 | 用途 |
|---|---|
| [OpenPrinting CUPS](https://openprinting.github.io/cups/) | 打印系统与设备/驱动基础 |
| [CUPS Printer Sharing](https://openprinting.github.io/cups/doc/sharing.html) | IPP 队列共享、队列 shared 属性和发现机制 |
| [CUPS Firewalls](https://openprinting.github.io/cups/doc/firewalls.html) | 打印和发现端口 |
| [CUPS IPP Implementation](https://openprinting.github.io/cups/doc/spec-ipp.html) | 任务状态、查询、创建/发送文档和控制操作 |
| [RFC 8011](https://www.rfc-editor.org/rfc/rfc8011.html) | IPP 属性组约束；同组属性名必须唯一 |
| [CUPS Policies](https://openprinting.github.io/cups/doc/policies.html) | 操作授权；需结合真实策略验证 |
| [cupsd.conf](https://openprinting.github.io/cups/doc/man-cupsd.conf.html) | 监听、访问、任务历史和文件保留 |
| [lpadmin](https://openprinting.github.io/cups/doc/man-lpadmin.html) | 队列配置与错误策略 |
| [OpenPrinting ipp-usb](https://github.com/OpenPrinting/ipp-usb) | IPP-over-USB 代理与本机设备接入 |
| [Microsoft Add-Printer](https://learn.microsoft.com/en-us/powershell/module/printmanagement/add-printer?view=windowsserver2025-ps) | IppURL 定向添加与 DeviceURL/WSD 的区别 |
| [Windows protected print mode](https://learn.microsoft.com/en-us/windows/modern-print/windows-protected-print-mode/windows-protected-print-mode) | 现代打印模式兼容边界 |
| [uv 项目指南](https://docs.astral.sh/uv/guides/projects/) | pyproject、项目环境、uv run/build 工作流 |
| [uv 项目配置](https://docs.astral.sh/uv/concepts/projects/config/) | Python 版本约束、CLI entry point 与构建系统 |
| [uv 锁定与同步](https://docs.astral.sh/uv/concepts/projects/sync/) | locked、extras、开发依赖、非 editable 部署 |
| [uv 依赖管理](https://docs.astral.sh/uv/concepts/projects/dependencies/) | 默认依赖、optional dependencies 与开发组 |
| [OpenPrinting pycups](https://github.com/OpenPrinting/pycups) | Python 的 libcups 绑定，原生依赖需在目标平台验证 |

官方文档说明协议和操作存在，不能证明这台 HP 4900 经此 CUPS 代理与所有 Windows 驱动兼容，也不能证明指定版本已完成实际出纸测试。

本地事实以[实机基线](00-current-device.md)和[P1 实测记录](verification/p1-20260929.md)为准：先前对话记录旧测试；P1 实测记录当前版本、备份、有限共享、防火墙边界、Windows 内置 IPP 类驱动作业及仍未修复的重复属性。CUPS 报告完成与纸张实物确认分别记录。

没有把相似型号的说明书当作本机自动双面/纸型能力依据；墨水读数是设备上报快照。也不把云端 Universal Print Connector 的版本前提套用成所有本地 IPP 打印的系统要求。
