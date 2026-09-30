# 实际进度

[返回主计划](README.md) · [实施阶段](06-roadmap-and-acceptance.md)

> 最后更新：2026-09-30。这里只记录实际完成事项，不把设计文本当作实现。

## RC9 新用户注册

只读确认公共 Authentik 注册 Flow 当前开放，返回用户名、邮箱、密码和确认密码表单。安装器新增“注册账号”、窗口内注册表单、邮件验证指引与限频重发；验证后回到正常登录，不直接授予打印权限。使用既有账号服务与邮箱准入规则，未修改 auth-login 工作树或生产配置。Windows 构建与既有 40 项 CI 检查通过，两端已发布同一安装包并校验公开下载；真实注册和邮件验证仍待实机验收。见 [RC9 记录](verification/windows-rc9-20260930.md)。

## RC8 登录表单与小图标

实验室 Logo 已从原图预生成 36、48、60、72、96、120、144、192 px，界面按 DPI 选图，标题栏使用多尺寸 ICO。修复输入框两层 Padding 叠加，隐藏空提示占位。密码和验证码在提交、错误重试中保留，完成认证或主动退出时清空；验证码标题改为“动态验证码(Authenticator)”。保留默认浅色与覆盖安装。Windows 构建、既有 40 项检查通过，两端 Release 已发布；GUI 交互待实机验收。见 [RC8 记录](verification/windows-rc8-20260930.md)。

## RC7 默认浅色

按用户最新要求，安装器默认使用白色 Light 主题，停止跟随 Windows 应用深浅色；图标和 Windows 11 标题栏采用浅色配色，保留系统高对比度支持。延续 RC6 覆盖安装逻辑。Windows 构建和既有 40 项检查通过，两端 Release 已发布；未执行 GUI 实机验收。构建与发布记录见 [RC7](verification/windows-rc7-20260930.md)。

## RC6 重复安装

修复只按本地端口记录判断同名队列的逻辑：支持识别并复用已有实验室打印机、恢复丢失的配置，保留队列与打印偏好。同一安装包再次安装时不替换相同 EXE、不重启后台；升级增加文件占用等待与失败恢复。GitHub 构建及既有 40 项检查通过，两端 Release 已发布，镜像下载校验一致。详见 [RC6 记录](verification/windows-rc6-20260930.md)。尚未进行重装实机验收。

## RC4 / RC5 界面与左栏状态

安装器已按 xju-feiyue 的 Notion 配色与控件间距调整，减少重复文案；应用改用用户提供的简约打印机图标，运行窗口和界面随系统深浅模式切换。左栏每 15 秒独立读取状态 API，显示设备、纸张和墨量，失败时静默显示旧读数或未知值。实验室名称改为“算法与科研实验室”，打印机名称保持“算法实验室·惠普打印机”。详见 [RC4 / RC5 记录](verification/windows-rc4-20260930.md)。Pi 生产保留 RC3，源码继续同步。

RC4 因图片下载元数据的文件名不兼容而未生成发布。修复后已发布 RC5；GitHub 构建成功，既有 CI 的 40 项检查通过，新 UI 和主题切换未进行实机验收。

## RC3 图形安装器与状态 API

已实现 C# WPF 自包含安装向导、窗口内 Authentik 账号密码/动态验证码/授权、图形状态及卸载入口。品牌统一“算法实验室”，Logo 使用用户提供图片。Python 打印后台与 Pi 原 CUPS/USB 链路继续保留。

RC3 已在 GitHub/GitCode 公开发布，同一 EXE（86,702,870 字节）和 SHA256；GitCode 公共下载与 GitHub 文件校验一致。安装包仍未签名。

公开只读 `/v1/status` 已在 Pi 部署并通过公网返回 JSON，15 秒缓存，物理设备与 CUPS 状态分别记录，未知墨量为 null。部署提交 `6c5ac0b`；读数为彩色 20%、黑色 50%，设备/CUPS 均 idle/none。本轮未手动运行测试，推送触发原有 CI 的 40 项检查通过；RC3 真人登录/打印仍需验收。构建、部署和双端发布事实记录在 [RC3 记录](verification/windows-rc3-20260930.md)。以下 RC2/P1 条目是既有基线。

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
| Authentik | 公共注册已开放；所有已激活且已验证邮箱的账号自动获得打印准入，无需管理员逐个审批；RC2 兼容 |
| Windows EXE | RC2 已完成安装；新命名队列使用内置 IPP 驱动，启动项和卸载入口已配置 |
| 公网 Windows 打印 | Windows job 5 → 公网 → CUPS job 4，CUPS completed；用户已确认测试页很快出纸，Word 文档和实际校外网络待验收 |
| GitHub / GitCode / Pi | 两端同名仓库公开，main/标签同步；RC2 同一 EXE 和 SHA256 双端发布，Pi 拉取 main；账号负责打印准入 |
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

已完成真实登录、系统队列和公网 Windows 系统打印验收，用户已确认测试页很快出纸；修复 JWKS 403、Windows 提权、IPP 队列名小写及中文设置编码问题。见 [RC2 实测](verification/windows-rc2-20260930.md)。Word 自动化未能完成，需人工 Ctrl+P 验收；实际校外网络仍待验证，尚未发布稳定版。

Windows 到树莓派现有 CUPS/USB 的系统打印主链路和本次实物出纸已经验证，可开始 P2（Python + uv 的只读核心与 CLI）。P1 的协议合规、稳定 WLAN 地址、元数据权限及 Word/PDF 兼容仍列为明确收尾项，不能写成完整发布验收通过。

P2 先建立根目录 uv 包和只读队列/作业 CLI，不安装或重建 CUPS；之后再逐阶段实现管理员控制、可靠文件打印、打包及部署。用户已确认的 LAN 直接打印和管理员管理需求不重复询问。
