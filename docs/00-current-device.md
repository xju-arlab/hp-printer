# 00 实机基线

[返回主计划](README.md) · [下一步 P1](06-roadmap-and-acceptance.md)

## 1. 证据与时间

本轮先读取 Codex 对话“检查树莓派打印机控制”（`01a0edef-cd90-7051-a7c2-45c3ee0d0b55`），再通过 SSH 只读检查设备。盘点时间约 **2026-09-29 16:47–16:50 UTC**；树莓派显示北京时间 **2026-09-30 00:47–00:50 +08:00**，两者为同一时间段。

先前对话记录：已安装配置打印服务，提交/查询/取消通过；1 页黑白测试任务被服务报告完成。该记录不替代纸张实际输出确认。本轮没有重新打印、重启服务、安装软件、修改网络或队列。

以下是当时观测值，不是永久地址或未来版本保证。后续每次实机实施先复核连接目标。

## 2. 设备与连接

| 项目 | 本轮观察 |
|---|---|
| 设备 | 用户确认 Raspberry Pi 4B；主机名 `fourb` |
| SSH 定位 | `winbeau@192.168.5.87`；凭据不写入项目 |
| 系统 | Ubuntu 24.04.4 LTS / Noble / `aarch64` |
| Python | 3.12.3；未安装 `python3-cups` 系统包 |
| 实验室 LAN | `wlan0 = 192.168.5.87/24` |
| 另一接口 | `eth0 = 192.168.137.2/24`；不等于已接入实验室有线 LAN |
| 路由 | 优先默认路由经 `192.168.5.1` / wlan0，另有 eth0 和 DHCP 默认路由 |
| USB | VID:PID `03f0:041b`，HP DeskJet 4900 series；不记录设备序列号 |
| 根文件系统 | 约 58G，总已用 16G，可用 41G；只是检查时快照 |
| 当前 Windows | Windows 11 家庭版中文版，版本 `10.0.26200` / build `26200` |
| 本机添加能力（P0 时） | `Add-Printer` 存在 `IppURL` 参数；当时尚未安装或验证新队列 |

## 3. 打印链路

```text
CUPS HP_DeskJet_4900
    → ipp://localhost:60000/ipp/print
    → ipp-usb
    → USB HP DeskJet 4900 series
```

| 项目 | 本轮观察 |
|---|---|
| CUPS | `2.4.7-1.2ubuntu7.14`，scheduler running |
| cups-filters | `2.0.0-0ubuntu4.1` |
| ipp-usb | `0.9.24-0ubuntu3.3` |
| avahi-daemon | `0.8-13ubuntu6.2` |
| 服务 | cups、ipp-usb、avahi-daemon 均 active |
| 队列 | `HP_DeskJet_4900`，enabled、accepting、idle；未完成任务数 0 |
| 队列 UUID | `urn:uuid:67cd2fe6-5447-3ddb-6acb-756a0120186b` |
| CUPS 设备 URI | `ipp://localhost:60000/ipp/print` |
| 驱动描述 | `Printer - IPP Everywhere` |
| 当前默认 | A4、黑白、单面、1 份、Normal、优先级 50、`job-hold-until=no-hold` |
| 其他队列选项 | `job-cancel-after=10800`；实施前核对实际超时语义，避免长时间缺纸后自动取消出乎预期 |

默认值和能力要从实际队列获取，不在代码里硬编码。

## 4. P0 时网络入口（P1 更新见第 7 节）

- CUPS 配置为 `Listen localhost:631` 与本地 socket；IPv4/IPv6 均只看到 loopback 631。
- `Browsing No`、`printer-is-shared=false`。从当前电脑的 WSL 请求 `192.168.5.87:631` 连接失败，符合尚未开放共享的状态。
- ipp-usb 配置为 `interface = loopback`、`dns-sd = enable`、端口范围 60000–65535。`ss` 显示 `*:60000`，但不能据此认定对外可用；LAN HTTP 请求未获得有效响应（curl exit 56）。P1 再检查绑定和访问限制，Windows 只接 CUPS 631 队列，不连接此设备代理端口。
- CUPS 的 `WebInterface Yes` 只代表服务启用了页面，不代表 LAN 已可访问。

当前地址没有确认 DHCP 保留或稳定 DNS，`fourb.local` 也未验证。安装文档将显式要求验证稳定地址。

## 5. 能力与异常

| 项目 | CUPS / USB 属性结果 | 实施含义 |
|---|---|---|
| 黑白/彩色 | 支持；当前黑白默认 | Windows 必须正确呈现并各测一次 |
| 双面 | 两侧均报告仅 `one-sided` | 不显示自动双面功能；人工翻页另行设计 |
| 纸张 | CUPS 含 A4、A5、A6、Letter 等 | 第一版先验收 A4；其他尺寸按需 |
| 份数 | CUPS 1–9999，USB 设备 1–99 | 能力并不等于政策上限；初版建议最多 20 份 |
| 文档格式 | CUPS 接受 PDF 等；USB 侧不报告 PDF，报告 PWG/URF/PCLm 等 | 必须保留 CUPS 过滤转换；不能把 PDF 直接发给 USB 端点 |
| 墨水 | 彩色 20%，黑色 50% | 设备估计快照；显示采样时间，不承诺实时精确 |
| USB 侧 IPP 检查 | `get-printer-attributes.test` PASS | 设备可查询，仍不代表全部打印功能已验收 |
| CUPS 侧 IPP 检查 | 同一测试 FAIL：重复 `media-default`、`sides-default` 属性 | P1 调查原因并重测，不能将有响应记为协议验收通过 |

## 6. P0 时尚未验证（历史快照；当前状态见第 7 节）

Windows 实际添加/驱动/Word 和 PDF 出纸、Windows protected print 设置、其他电脑版本、跨客户端队列控制、掉电恢复、缺纸恢复、USB 重插、重启后端口稳定性、服务权限与完整备份均未验证。

当时新 SSH 会话的非交互 sudo 检查失败，不能据此假设部署账号有免密管理权限。P1 后续通过正常的本机管理员认证完成受限变更；不要把凭据放入安装脚本或命令日志。

只读检查来源包括 `lpstat`、`lpoptions`、`ipptool Get-Printer-Attributes`、包版本、服务状态、USB/网络/磁盘状态和可读配置项。未读取任务正文和 spool 文件，未备份受限配置，因此 P0 完成的是盘点，P1 变更前仍需备份。

## 7. P1 实测结果（2026-09-29 / Pi 2026-09-30 +08:00）

复用已授权 SSH/tmux 会话后确认设备仍为 `fourb`、Pi 4B、Ubuntu 24.04.4 LTS/aarch64。CUPS `2.4.7-1.2ubuntu7.14`、cups-filters `2.0.0-0ubuntu4.1`、ipp-usb `0.9.24-0ubuntu3.3`、Avahi `0.8-13ubuntu6.2`；HP USB `03f0:041b` 在线。原 `HP_DeskJet_4900 → ipp://localhost:60000/ipp/print` 队列保留。

变更前的 `cupsd.conf`、`printers.conf`、队列 PPD、`ipp-usb.conf` 已备份到 Pi 上权限 700 的 `/home/winbeau/hp-printer-backups/p1-20260929/`（文件 600）。CUPS 现绑定 WLAN `192.168.5.87:631`，目标队列仅向 `192.168.5.0/24` 共享；管理/配置仅留在 loopback。Windows `192.168.5.71` 可连 631，不能连 60000；Pi 直连接口 `192.168.137.2` 不提供这两个端口。尽管 ipp-usb 配置设为 loopback，运行进程仍监听 `*:60000`，已用 systemd ExecStartPre 加 nftables 入站保护，阻止非 loopback 到 TCP 60000–65535；CUPS 本机代理链路仍可用。CUPS `/admin`、`/admin/conf` 从 Windows 返回 403。

IPP 原始 USB 端点的 `media-default`、`sides-default` 各一次；CUPS 生产队列各两次。临时 driverless 对照队列应用相同 A4/单面/黑白选项后仍各一次；重生成生产 PPD、重启服务也未消除重复。因此定位到 CUPS 生产队列响应路径，但精确原因仍未知，协议检查保持失败。Windows 本次 Validate-Job 与实际提交未被重复属性阻断。

Windows 11 build 26200 已新增 `HP DeskJet 4900 (Pi CUPS)`，使用 Windows inbox Microsoft IPP Class Driver，不需要 HP 厂商驱动。默认 A4/黑白/单面，Windows 能力中有彩色/灰度/黑白；CUPS 报告支持 300 dpi 和单面。原有 WSD/USB 队列和 USB 默认值未改变。Windows job 4 经 Pi CUPS 生成 job 3，Validate/Create/Send 成功，CUPS 报告完成并回到 idle；原始 USB 状态为 idle/none，CUPS 自身却残留 `media-empty-report`，但用户已确认测试页实际出纸。当前 `192.168.5.87` 未验证 DHCP 保留/长期稳定；IPP Get-Jobs/Get-Job 权限、Word/PDF、protected print 和其他客户端仍待验证。详见 [P1 实测记录](verification/p1-20260929.md)。
