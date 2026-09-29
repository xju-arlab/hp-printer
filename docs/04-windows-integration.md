# 04 Windows 系统打印机接入

[返回主计划](README.md) · [实机基线](00-current-device.md)

## 1. 目标与当前差距

Word、PDF 阅读器和浏览器选择“实验室 HP 4900”即可打印，任务进入树莓派同一 CUPS 队列。管理员使用 CLI 查看和控制任务；CLI 文件打印作为另一个提交入口，不影响 Windows 原生打印流程。

当前电脑为 Windows 11 build 26200，已新增 `HP DeskJet 4900 (Pi CUPS)` 系统队列并提交一项测试作业到树莓派。该队列使用 Windows 自带的 Microsoft IPP Class Driver；无需单独下载或安装 HP 厂商驱动。原有 WSD 与 USB 队列、原默认值均保留。CUPS 报告测试作业完成，用户确认测试页实际出纸。其他 Windows 10/11 设备仍需另行测试。

## 2. 地址与协议

对外目标为 **树莓派 CUPS 的队列地址**，计划示例：

```text
IPP URI:  ipp://<稳定主机名或地址>:631/printers/HP_DeskJet_4900
HTTP URL: http://<稳定主机名或地址>:631/printers/HP_DeskJet_4900
```

后续提供 IPPS 时验证证书主机名、信任链和 Windows 协议支持。当前 `192.168.5.87` 只是观测地址，没有确认长期稳定。`localhost:60000/ipp/print` 是 Pi 上 USB 代理的内部地址，不能让 Windows 直接使用；也不把打印机自身的 Wi-Fi 地址作为入口。

CUPS 原生使用 IPP 共享并支持 DNS-SD 发现。项目首选明确 URL 添加，再考虑自动发现；无需为首版引入 Samba。[CUPS Printer Sharing](https://openprinting.github.io/cups/doc/sharing.html)

## 3. P1 执行顺序

1. 已复核现有 USB 队列和活动作业，备份了 CUPS/ipp-usb/队列配置。重复属性位于 CUPS 队列响应；受控临时队列未复现，准确根因待查，严格查询仍失败。
2. 以当前 WLAN 地址 `192.168.5.87`（尚未证明稳定）和 `192.168.5.0/24` 配置唯一队列共享。TCP 631 仅绑定 WLAN；CUPS 管理页面/配置接口仅允许 loopback。Pi 直连接口不开放 CUPS。
3. Windows WLAN 到 TCP 631 可达、到 ipp-usb TCP 60000 不可达；Pi 本机仍可经 `localhost:60000` 转发。另加 systemd/nftables 持久化保护，避免 ipp-usb 的 `*:60000` 监听暴露给 LAN。[CUPS 防火墙说明](https://openprinting.github.io/cups/doc/firewalls.html)
4. Windows 可访问打印资源；`/admin`、`/admin/conf` 返回 403。匿名 `/jobs?which_jobs=completed` 页面返回 200，但未列出本次作业标题/编号；IPP `Get-Jobs`/`Get-Job` 权限仍需单独验收。
5. 已添加新系统队列并保留原队列与默认值。Windows 默认 A4、黑白、单面，并报告 Color/Grayscale/Monochrome 选项；CUPS 仅声明单面，接受 PDF/PCLm/PWG Raster、300 dpi。记录见 [P1 实测](verification/p1-20260929.md)。
6. 当前 Windows 提交的作业由 CUPS 报告完成，且用户确认测试页实际出纸。重复属性仍不符合 RFC 8011；本次 Windows 成功不等同于协议修复或全平台兼容，P1 发布门槛仍有收尾项。

## 4. 添加方式与脚本封装

Microsoft 的 `Add-Printer -IppURL` 用于 IPP 定向发现，`-DeviceURL` 属于 WSD，二者不能混用。[Add-Printer 官方文档](https://learn.microsoft.com/en-us/powershell/module/printmanagement/add-printer?view=windowsserver2025-ps)

本轮执行的调用（通过 Windows UAC 安装流程）：

```powershell
$printerUrl = 'http://192.168.5.87:631/printers/HP_DeskJet_4900'
Add-Printer -Name 'HP DeskJet 4900 (Pi CUPS)' -IppURL $printerUrl
```

如果目标系统没有该参数，先验证设置界面的 IPP 添加流程，单独记录该版本支持的安装途径。不要自动启用所有旧版打印组件或改用任意 Raw TCP/9100 驱动；当前 CUPS/IPP 地址不是 JetDirect 端口。

| 拟实现脚本 | 职责 |
|---|---|
| `Test-LabPrinter.ps1` | 只读检查系统/build、PrintManagement 能力、地址/IPP、已装队列与驱动，输出人类摘要和 JSON；默认不打印 |
| `Add-LabPrinter.ps1` | 验证 URI 和本机能力；同名同目标幂等；同名异目标报冲突；支持 WhatIf；不更改系统默认打印机 |
| `Remove-LabPrinter.ps1` | 只删除匹配项目安装记录及目标 URL 的本机队列；检查未完成任务；不删除共用驱动/其他队列 |

脚本接受参数并记录安装清单，不硬编码当前 IP。提权仅限确有需要的本机安装步骤；连接诊断无需永久管理员运行。无静默测试打印，也不默认清空 Windows spooler。

## 5. 驱动和 Windows protected print

“免装厂商驱动”不意味着客户端完全没有打印组件：Windows 使用操作系统自带的 Microsoft IPP Class Driver，Pi 端 CUPS/ipp-usb 负责队列、过滤和 USB 设备连接。本次 Windows 队列实测使用该 inbox 类驱动，未安装 HP 厂商包；单次成功不自动证明所有应用选项或受保护打印均兼容。

Windows protected print 使用受支持的现代打印路径；实际是否启用、设备/代理是否兼容需单独验证。脚本不能关闭该模式或组织策略来“修复”连接，也不自行安装未经验证的第三方驱动。[Windows protected print 官方说明](https://learn.microsoft.com/en-us/windows/modern-print/windows-protected-print-mode/windows-protected-print-mode)

失败时按地址/访问 → IPP 响应 → 驱动协商 → 文档格式 → 设备输出的顺序定位。SMB 只作为后续经验证的兼容选项，不是默认解决办法。

## 6. 最小验收矩阵

| 用例 | 通过证据 |
|---|---|
| 一台实际 Windows 添加 | 已完成：系统队列存在，IPP 作业到达 Pi CUPS；记录 build/驱动/URL |
| Word 黑白 A4、PDF A4 | 待验证：各有可识别 CUPS 任务并人工确认纸张完整；不能只看系统显示完成 |
| 彩色、2 份 | 实际输出符合选项；记录耗材/测试纸张数量 |
| 单面能力 | 不误报自动双面；默认 A4/黑白与设备一致 |
| 两台客户端并发 | 两个原生任务出现在同一 CUPS 队列；无第二套直连设备队列 |
| Pi 暂不可达 | 明确任务仍在 Windows 本机还是已送达；恢复后未产生意外重复任务 |
| 管理暂停/取消/恢复 | 观察 CUPS 和 Windows 状态；终态任务不能伪装为可恢复 |
| 重启 Pi/USB 重插 | 队列目标可恢复；内部代理端口变化有明确诊断，不重建公共队列应急 |

单台 Windows 成功后可先进入 P2，但第二客户端和故障用例仍保留为发布门槛，不能标成已完成。
