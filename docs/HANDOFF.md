# 新对话交接说明

[计划索引](README.md) · [进度](progress.md) · [Windows 与公网](09-windows-release.md)

## 当前目标与范围

用户将以下内容提前：Windows EXE 安装器、Authentik 登录与邮箱/打印组准入、校外 Word Ctrl+P、私有 GitHub Release、本地和 Pi 版本同步。纯 Python + uv，无前端工程，无 HP 专有驱动安装。网页上传、DOCX 转换/字体和完整 CLI 队列管理仍为后续阶段。

## 已落地

- 本地 `/home/winbeau/xju-arlab/hp-printer`，私有仓库 `https://github.com/xju-arlab/hp-printer`，主分支 main；Pi 同路径 clone。版本以 GitHub 为准，本地 commit/push 后用 `scripts/sync-pi.sh` 拉取，再在 Pi 执行 `scripts/install-pi.sh`。
- Pi `winbeau@192.168.5.87`，主机 fourb，Ubuntu 24.04.4 arm64。原 `HP_DeskJet_4900 → ipp://localhost:60000/ipp/print → USB` 保留。P1 备份 `/home/winbeau/hp-printer-backups/p1-20260929/`。
- CUPS 只在 loopback 和 WLAN 192.168.5.87:631 服务；192.168.5.0/24 直接打印，管理页面限 loopback，ipp-usb 外部端口有 nftables 保护。WLAN DHCP 保留仍未确认。
- Python 网关由 systemd `hp-printer.service` 运行，监听 127.0.0.1:8765。现有 Cloudflare Tunnel 将 hp.icthub.top 转发至此。`/health` 已公网返回 200，匿名 IPP 返回 401。
- Authentik 位于 huawei2 的 Docker 部署。本仓库 `deploy/authentik-hp-printer.yaml` 已应用并作为数据库 BlueprintInstance 持久化。用户指定 `winbeau` 为首个打印授权成员，已加入 hp-printer-users。相邻 auth-login 工作区已有未提交变更，不修改它。
- Windows 安装器使用 public OIDC client + PKCE，回调 127.0.0.1:18766；当前用户 DPAPI 保存令牌。后台桥 127.0.0.1:18765，优先探测 LAN CUPS UUID，其他情况通过 HTTPS 公网网关；无需客户端 cloudflared。
- 目标 Windows 设备名“算法实验室·惠普打印机”，内置 Microsoft IPP Class Driver，当前用户登录时自动启动。安装器代码和 EXE 构建已完成，真实用户登录流程尚待完成。
- 私有 Release v0.1.0-rc.1 已发布，含 GitHub 构建并核对 SHA256 的 EXE。该标签固定 dc74df4，后续文档记录继续同步 main；不得将候选版写成通过 Windows 端到端验收。
- 既有 Windows P1 队列 `HP DeskJet 4900 (Pi CUPS)` 已实际打印，用户确认出纸。这个事实不能替代新安装器和公网路径验收。原 USB 默认打印机不更改。

## 验收与已知限制

详细证据以 [本轮记录](verification/windows-release-20260929.md) 为准。首次浏览器授权等待超时，不能把新版打印机安装或公网 Word 打印标为完成。下一步让用户在系统浏览器完成 winbeau 登录，检查新队列、后台自启/刷新、LAN 与强制公网的合成文档；实物出纸另由用户确认。

公网限制每次 IPP 请求 80 MiB；账号须有已验证邮箱与打印组。服务端检查 JWT 和作业所有权，不信任客户端自报用户名。已提交请求失败后不自动换路重发。CUPS 是唯一调度者。

CUPS 生产响应重复 media-default/sides-default 尚未根治，Windows 桥过滤相同重复默认值。CUPS 曾报告 media-empty-report，原 USB 接口却 idle/none；仍需观察。protected print、实际校外网络和更多 Windows 客户端未验证。EXE 当前无代码签名证书。

## 运维注意

组织禁止 deploy keys；同步使用本机 gh 现有授权，通过 SSH stdin 临时传给 Pi 进程，凭据不落盘。同步/下载可经 Windows LAN 代理 192.168.5.71:10808。已部署网关独立于本机代理运行。Pi sudo 非免密，凭据不进 Git 或日志。

生产使用 `/opt/hp-printer/releases/<commit>` 不可变目录和 current 链接，uv --locked 安装；健康检查失败回退上个版本。GitHub 标签流水线先构建草稿 Release，审核真实验收结果后发布。

## 后续继续提示

> 先读 docs/README.md、docs/HANDOFF.md、docs/08-cli-and-uv.md、docs/progress.md 和本轮实测记录。私有候选版 v0.1.0-rc.1 已发布，继续完成 Windows 登录、安装、公网 Word 打印验收，通过后发布稳定版；保持本地、GitHub、Pi 的 main 相同提交。随后再逐阶段补齐 CLI 打印和队列管理，不重建 CUPS/USB、不引入前端，也不把待验收项写成完成。
