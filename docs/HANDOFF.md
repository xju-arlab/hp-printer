# 新对话交接说明

[计划索引](README.md) · [进度](progress.md) · [Windows 与公网](09-windows-release.md)

## 当前目标与范围

最新 UI 要求：参考 xju-feiyue 的 Notion 风格，减少提示，左栏显示实时打印机状态；实验室名称为“算法与科研实验室”，设备名仍为“算法实验室·惠普打印机”。RC4 / RC5 说明见 [记录](verification/windows-rc4-20260930.md)。这是对 RC3 品牌文案的后续修正。

最新公开客户端为 RC5，提交 `25da32040ace83ce93b9abc3222df27b4d7beb4c`。应用使用简约打印机图标，运行窗口和界面随 Windows 应用主题切换，实验室徽标保留在左栏。RC4 构建被图片附带元数据路径阻断，未发布；标签保留。生产 API 仍固定 RC3，GUI/主题、登录和升级待真人验收。

用户将以下内容提前：Windows EXE 安装器、Authentik 登录与邮箱验证、校外 Word Ctrl+P、GitHub/GitCode 公开仓库与 Release、本地和 Pi 版本同步。用户已明确改为公开下载，打印准入由账号执行；实验室内网保持直接打印。客户端采用 C# WPF 图形安装器、窗口内登录，实验室品牌为“算法与科研实验室”，采用用户 Logo；Pi/打印桥继续 Python + uv。用户明确 `/v1/status` 是状态 API，不做状态页。网页上传、DOCX 转换/字体和完整 CLI 队列管理仍为后续阶段。

RC3 新代码与构建见 [记录](verification/windows-rc3-20260930.md)。登录 UI 使用 Authentik Flow Executor + PKCE，不监听 18766，Python CLI 的旧浏览器入口保留兼容。新 GUI 真人登录、升级/卸载、Word 和校外网络尚未验收，不要套用 RC2 的成功证据。SignPath 未完成，EXE 尚未签名。

Pi 生产已由 RC2 升级至 `6c5ac0bc296af2f16094ee10f2b42d5c5f6abba2`（0.1.0rc3），`/health` 与公开 `/v1/status` 在线。物理设备和 CUPS 返回空闲、none，彩色 20%/黑色 50%。此处是新基线，下面 RC2 的打印实测仍是历史证据。

GitHub/GitCode 的 `v0.1.0-rc.3` 已公开发布同一 WPF EXE 和校验文件，文件校验见 RC3 记录。维护文档可继续在 main 更新；Pi 生产程序固定在该 tag 对应提交，不因文档提交重新部署。

## 已落地

- 本地 `/home/winbeau/xju-arlab/hp-printer`，公开仓库 `https://github.com/xju-arlab/hp-printer` 与 `https://gitcode.com/xju-arlab/hp-printer`，主分支 main；本地 remote 分别为 origin/gitcode，Pi 同路径 clone。版本以 GitHub 为准，本地 commit 后推送两端，用 `scripts/sync-pi.sh` 拉取；需要部署代码时再在 Pi 执行 `scripts/install-pi.sh`。RC2 在两端发布相同 EXE/SHA256，镜像不另行构建。
- Pi `winbeau@192.168.5.87`，主机 fourb，Ubuntu 24.04.4 arm64。原 `HP_DeskJet_4900 → ipp://localhost:60000/ipp/print → USB` 保留。P1 备份 `/home/winbeau/hp-printer-backups/p1-20260929/`。
- CUPS 只在 loopback 和 WLAN 192.168.5.87:631 服务；192.168.5.0/24 直接打印，管理页面限 loopback，ipp-usb 外部端口有 nftables 保护。WLAN DHCP 保留仍未确认。
- Python 网关由 systemd `hp-printer.service` 运行，监听 127.0.0.1:8765。现有 Cloudflare Tunnel 将 hp.icthub.top 转发至此。`/health` 已公网返回 200，匿名 IPP 返回 401。
- Authentik 位于 huawei2 的 Docker 部署。本仓库 `deploy/authentik-hp-printer.yaml` 已应用并作为数据库 BlueprintInstance 持久化。用户随后明确开放打印准入：所有已激活且邮箱已验证的 ICTHub 账号自动获得该应用的打印权限。专属 groups scope 保留 RC2 兼容的 hp-printer-users claim，不要求逐个加入真实组。相邻 auth-login 工作区已有未提交变更，不修改它。
- Windows 安装器使用 public OIDC client + PKCE，回调 127.0.0.1:18766；当前用户 DPAPI 保存令牌。后台桥 127.0.0.1:18765，优先探测 LAN CUPS UUID，其他情况通过 HTTPS 公网网关；无需客户端 cloudflared。
- Windows 已安装“算法实验室·惠普打印机”，内置 Microsoft IPP Class Driver。真实登录、授权刷新、Startup 快捷方式恢复已验证，默认仍为原 USB 打印机。端口 WSD-d4e26a22-14b1-4ca0-8bad-cb9428791b98。
- 已完成一页公网 Windows 系统打印：Windows job 5 → remote → CUPS job 4，Get-Job-Attributes 返回 completed，用户确认测试页很快出纸。测试后已恢复内网优先。RC2（0.1.0rc2）修复并替代 RC1；旧标签和资产保留。
- 既有 Windows P1 队列 `HP DeskJet 4900 (Pi CUPS)` 已实际打印，用户确认出纸。这个事实不能替代新安装器和公网路径验收。原 USB 默认打印机不更改。

## 验收与已知限制

2026-09-30 已按用户要求开放打印准入，部署与回退见 [开放准入记录](verification/open-registration-20260930.md)。反馈账号原先缺少人工打印组，现在符合新的准入条件；需从安装器重新发起登录，旧拒绝页面不代表新授权结果。

详细证据以 [RC2 实测](verification/windows-rc2-20260930.md) 为准。登录、安装、公网系统打印、自启和刷新已验证。Word 自动化保存失败/未完成，未执行到 Word PrintOut；需用户手动 Ctrl+P 验收。用户已确认新测试页很快出纸，字体细节未单独确认；实际校外网络另测。不要把 GDI 系统打印成功写成 Word 已打印成功。

公网限制每次 IPP 请求 80 MiB；账号须已激活且邮箱已验证；打印权限由本应用的 OIDC mapping 自动授予，无需管理员逐个审批。服务端检查 JWT 和作业所有权，不信任客户端自报用户名。已提交请求失败后不自动换路重发。CUPS 是唯一调度者。

CUPS 生产响应重复 media-default/sides-default 尚未根治，Windows 桥过滤相同重复默认值。CUPS 曾报告 media-empty-report，原 USB 接口却 idle/none；仍需观察。protected print、实际校外网络和更多 Windows 客户端未验证。EXE 当前无代码签名证书。

## 运维注意

组织禁止 deploy keys；同步使用本机 gh 现有授权，通过 SSH stdin 临时传给 Pi 进程，凭据不落盘。同步/下载可经 Windows LAN 代理 192.168.5.71:10808。已部署网关独立于本机代理运行。Pi sudo 非免密，凭据不进 Git 或日志。

生产使用 `/opt/hp-printer/releases/<commit>` 不可变目录和 current 链接，uv --locked 安装；健康检查失败回退上个版本。GitHub 标签流水线先构建草稿 Release，审核真实验收结果后发布。

本次 Windows 的 wsl.exe 启动命令挂起，WSL 文件系统与 SSH 服务仍正常；可通过 `ssh -p 2222 winbeau@127.0.0.1` 进入同一个 WSL，再调用 tmux helper 和同步脚本。不要重启 WSL 或终止其他项目进程。Windows Git 使用单次 safe.directory 参数处理 UNC 所有权检查。

## 后续继续提示

> 先读 docs/README.md、docs/HANDOFF.md、docs/08-cli-and-uv.md、docs/progress.md 和 RC2 实测记录。登录、Windows 安装及公网系统打印已通过，用户已确认测试页很快出纸；继续人工 Word Ctrl+P 和实际校外网络验收，再发布稳定版。保持本地、GitHub、Pi 的 main 对齐，逐阶段补齐 CLI 打印和队列管理。
