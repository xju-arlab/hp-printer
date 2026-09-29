# 实际进度

[返回主计划](README.md) · [实施阶段](06-roadmap-and-acceptance.md)

> 最后更新：2026-09-29（Pi 本地时间 2026-09-30）。这里只记录实际完成事项，不把设计文本当作实现。

## 当前状态

| 项目 | 状态 |
|---|---|
| 独立目录 hp-printer/docs | 已创建 |
| 需求与技术方案 | 已更新 v0.3：纯 Python + uv + CLI，无前端阶段 |
| P0 实机基线 | 已完成 |
| P1 Pi 链路复核与备份 | 完成；原 CUPS/USB 队列保留，配置备份位于 Pi 管理员目录 |
| P1 LAN CUPS 共享 | 完成；仅绑定当前 WLAN 地址与批准网段；ipp-usb 外部端口已用 nftables 隔离 |
| P1 Windows 系统打印机 | 已添加新队列，使用 Windows 自带 Microsoft IPP Class Driver；HP 厂商驱动未安装 |
| P1 Windows → Pi 作业 | Windows/CUPS 均报告完成，用户确认测试页已出纸；USB 原始端点为 idle/none，但 CUPS 原因仍为 `media-empty-report` |
| IPP 严格协议检查 | 已定位到 CUPS 生产队列响应层；重复默认属性仍未修复，Windows 本次提交未被阻断 |
| P1 其他待验收 | 稳定 WLAN 地址、IPP Get-Jobs/Get-Job 权限、Word/PDF、protected print 和更多客户端未验证 |
| Python + uv 基础 | 已实现包、锁文件、help/version、doctor、serve；完整队列/文件 CLI 待实现 |
| 公网网关 | 已部署，HTTPS health 200，匿名 IPP 401，原 CUPS/USB 保留 |
| Authentik | 独立应用和打印组已配置；winbeau 已授权；真实浏览器登录待完成 |
| Windows EXE | 已构建；新命名队列与公网 Word 打印待登录后验收 |
| GitHub / Pi | 私有仓库已建立，本地提交和 Pi 拉取已打通；v0.1.0-rc.1 候选版已发布 |
| 后续 | CLI 队列管理、可靠文件提交、网页上传/DOCX 和 LabOS 分阶段实现 |

## 本轮 P1 实施

- 复核 Raspberry Pi 4B / Ubuntu 24.04.4 arm64、CUPS 2.4.7、ipp-usb 0.9.24、Avahi 0.8；HP USB 设备在线，原 `HP_DeskJet_4900 → ipp://localhost:60000/ipp/print → USB` 队列保留。
- 变更前备份 `cupsd.conf`、`printers.conf`、队列 PPD 和 `ipp-usb.conf` 至 Pi 上权限受限的 `/home/winbeau/hp-printer-backups/p1-20260929/`。
- 将 CUPS 监听限制到 WLAN 地址 `192.168.5.87:631`，只允许 `192.168.5.0/24` 打印；管理页面仍限 loopback/系统管理员。Windows 能访问 TCP 631，不能访问内部 60000；Pi 直连接口 `.137.2` 不提供 CUPS。
- 发现 ipp-usb 虽配置 loopback，仍监听 `*:60000`。新增 systemd ExecStartPre nftables 保护，使非 loopback 来源到 TCP 60000–65535 被丢弃；重启后规则存在，CUPS 本机到 USB 代理链路正常。
- Windows 11 build 26200 新增 `HP DeskJet 4900 (Pi CUPS)`。驱动为 Windows 内置 Microsoft IPP Class Driver，内部显示为 IPP 类型的 WSD 端口。原 WSD/USB 队列未改，默认仍为原 USB 打印机。
- Windows job ID 4 / CUPS job ID 3 的一页非敏感测试被 CUPS 接收，IPP `Validate-Job`、`Create-Job`、`Send-Document` 均成功；CUPS 随后 idle。用户确认测试页已实际出纸。测试后 USB 原始 IPP 显示 idle/none，而 CUPS 队列原因显示 `media-empty-report`，该状态差异未解释。没有读取或打印用户文档。
- 严格 `Get-Printer-Attributes` 仍报重复 `media-default` 和 `sides-default`。USB 侧各一次；CUPS 队列侧各两次。受控临时队列加相同 A4/单面/黑白选项后仍各一次，因此精确根因未查明；Windows 本次的验证与作业提交成功，但不将异常记为协议修复。

实测和回退细节见 [P1 记录](verification/p1-20260929.md)。

## 阶段判定与下一步

### 用户追加的优先范围

已提前实现 Windows 安装包与公网 IPP 通路代码。首次安装等待浏览器授权超时，当前不能认定新队列或公网 Word 打印成功。私有 [v0.1.0-rc.1 候选版](https://github.com/xju-arlab/hp-printer/releases/tag/v0.1.0-rc.1) 已发布，包含 GitHub 构建的 EXE 和 SHA256。详见 [Windows 发布实测](verification/windows-release-20260929.md)；待用户完成账号授权后继续安装与作业验收，通过后再发布稳定版。

Windows 到树莓派现有 CUPS/USB 的系统打印主链路和本次实物出纸已经验证，可开始 P2（Python + uv 的只读核心与 CLI）。P1 的协议合规、稳定 WLAN 地址、元数据权限及 Word/PDF 兼容仍列为明确收尾项，不能写成完整发布验收通过。

P2 先建立根目录 uv 包和只读队列/作业 CLI，不安装或重建 CUPS；之后再逐阶段实现管理员控制、可靠文件打印、打包及部署。用户已确认的 LAN 直接打印和管理员管理需求不重复询问。
