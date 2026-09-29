# 新对话交接说明

[计划索引](README.md) · [进度](progress.md) · [实机基线](00-current-device.md)

## 1. 工作位置与已完成事项

项目位于 `/home/winbeau/xju-arlab/hp-printer`，与 `xju-lab`、`xju-feiyue` 同级。Windows 可通过 WSL 共享目录访问。

当前仍只有项目说明和设计文档，没有 Python 包、CLI、后端服务或安装脚本。P1 已在 Pi 上完成受限 CUPS 共享和内部 ipp-usb 端口保护；Windows 新队列已提交一项作业，详见 [P1 实测记录](verification/p1-20260929.md)。

用户最新要求已覆盖旧方案：**纯 Python 后端 + uv 工程 + CLI 打印，不开发前端**。根目录采用 pyproject.toml、uv.lock、src/hp_printer/，不建 frontend/backend 双工程，不引入 Node/pnpm。建议 Typer + FastAPI + pycups + SQLite + systemd，详见 [08 CLI 与 uv](08-cli-and-uv.md)。相邻 xju-lab 的代码不在本项目修改范围。

## 2. 必须继承的事实

- Raspberry Pi 4B，主机 `fourb`；本轮地址 `winbeau@192.168.5.87`，Ubuntu 24.04.4 arm64。
- HP DeskJet 4900 series 通过 USB 连接；现有队列 `HP_DeskJet_4900` → `ipp://localhost:60000/ipp/print` → ipp-usb。
- 默认自动打印，管理员可暂停、取消、恢复；第一版实验室 LAN，Windows 系统打印机优先。
- 权限已确认：实验室 LAN 电脑直接打印，管理员登录管理，首版不要求逐人认证。
- 管理员改为 CLI 登录；提供文件打印、查询、取消、挂起/释放、暂停/恢复、诊断命令。CLI/API 与 Windows 共用唯一 CUPS 队列。
- CUPS 原队列和 USB 链路已保留；当前仅在 Pi WLAN `192.168.5.87:631` 服务 `192.168.5.0/24`，管理配置仅 loopback。该地址尚未确认 DHCP 保留。
- USB 原始 IPP 侧查询通过；CUPS 生产队列仍重复 `media-default`/`sides-default`。重复原因定位到 CUPS 队列响应路径但尚未修复；Windows 当前 build 26200 已通过内置 Microsoft IPP Class Driver 完成一项作业提交。
- 原 Windows WSD/USB 打印队列均保留，USB 队列仍是默认；新队列为 `HP DeskJet 4900 (Pi CUPS)`，使用系统自带 Microsoft IPP Class Driver。CUPS 报告测试作业完成，用户确认测试页实际出纸。
- `/admin`、`/admin/conf` 从 WLAN 返回 403；匿名 completed jobs 页面没有列出本次任务，但 IPP `Get-Jobs`/`Get-Job` 权限范围仍待单独验证。其他应用/系统兼容、protected print、Word/PDF 待后续验收。
- CUPS 是唯一实际调度者；服务同步所有原生 IPP 任务，不创建另一个直接控制 USB 的执行队列。
- 原生用户名不作为可信成员身份；不得靠重新提交来掩盖上游超时或未知打印状态。

连接信息来自已授权的先前对话，凭据不在项目中。活动 SSH 连接可能过期；先验证连接，不把认证失败误诊成设备离线。修改配置前需要正常的管理员认证，当前账号并未证明具备免密 sudo。

## 3. 当前阶段与下一步

P1 Windows→Pi CUPS→USB 主链路已验证，下一步按阶段开始 P2：创建根目录 Python + uv 包、CLI help/version、配置加载及只读 CUPS 状态/作业查询。不要先建前端或重建系统打印队列。

P1 后续收尾仍要跟踪：查明并修复 CUPS 重复默认属性（严格 IPP 检查失败）；核验 WLAN 地址稳定性和 IPP `Get-Jobs`/`Get-Job` 权限范围；验证 Word/PDF、protected print 和其他 Windows 客户端。测试页实物出纸已由用户确认。Pi 备份与当前回退步骤见 [P1 实测记录](verification/p1-20260929.md)。复用既有 SSH/tmux 会话时先检查连接状态；不在聊天或项目里记录凭据。

若端到端步骤因现场权限/地址受阻，按真实子步记录，不把“端口可达”写成 Windows 打印成功。用户已回答的硬件、自动打印、LAN 直接打印/管理员登录和优先入口不要再问。

## 4. 可复制启动提示词

> 在 hp-printer 项目继续开发，纯 Python + uv，支持 CLI 打印，不做前端。先读 docs/README.md、docs/HANDOFF.md、docs/08-cli-and-uv.md 和 docs/progress.md。P1 Windows→Pi CUPS→USB 主链路已有实测，但 IPP 重复属性、纸张目视确认、稳定地址与兼容收尾仍未完成；先核实并处理这些收尾项，再按 docs/06-roadmap-and-acceptance.md 逐阶段实现后端和 CLI。不要安装 HP 厂商驱动或开发前端。
