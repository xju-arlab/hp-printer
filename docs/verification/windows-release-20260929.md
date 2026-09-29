# Windows 安装包与公网网关实测

记录日期：2026-09-29（Pi 当地为 2026-09-30）。此记录区分软件检查、服务部署、Windows 实际安装和纸张确认。

## 已确认

| 检查 | 结果 |
|---|---|
| 私有 GitHub 仓库 | xju-arlab/hp-printer 已创建，main 已推送 |
| Pi 版本同步 | 通过本机 gh 授权及 SSH stdin 拉取成功；Pi 不保存 GitHub token |
| 初次部署 | 2862d45ed395ec14d5688a604cf3dee89d3fd846，Python 3.12.3 / uv 0.9.17 |
| systemd | hp-printer 与 cloudflared 均 active |
| 公网健康检查 | https://hp.icthub.top/health 返回 200，版本 0.1.0 与部署 revision |
| 公网匿名访问 | /ipp/print 和 /v1/me 均 401 |
| 原始队列 | doctor 返回 IPP 成功，HP_DeskJet_4900 存在，CUPS 原因 media-empty-report |
| Authentik | 独立 public PKCE provider、邮箱/组约束、打印组已配置；winbeau 入组 |
| OIDC 配置 | discovery、JWKS 可访问；issuer 和 S256 正确 |
| 初版 Windows 构建 | Python 3.12.10、PyInstaller 6.22.3；EXE --version 返回 0.1.0 |
| Windows 凭据 | DPAPI 合成数据加解密往返通过，不涉及真实凭据输出 |
| 自动检查 | 本地 33 项通过；已推送的初版 27 项 GitHub Checks 通过 |

自动检查覆盖 JWT 签名/issuer/audience/期限/nonce/组/邮箱、IPP 文档字节保留、禁止操作、作业权限、上传限制、模糊失败不自动重发、LAN UUID 识别与路由固定、本机浏览器来源拒绝。它们不替代真实驱动及纸张验收。

## 尚待现场完成

- EXE 已发起系统浏览器登录，首次 10 分钟等待超时；尚未取得真实账号的授权回调。未伪造用户会话或绕过登录准入。
- 新设备“算法实验室·惠普打印机”尚未实际添加。原 P1 队列保留，默认打印机未改。
- 新版安装、自启/登录续期、Word Ctrl+P、LAN 与强制公网合成文档提交均待验证。
- 实际校外网络和真实纸张输出尚未验收；后续即使 CUPS completed，也需用户另行目视确认。

## 已知边界

- 当前 EXE 未签名，Windows 可能提示未知发布者。
- 后台属于安装用户，随该用户登录启动；每次 IPP 请求上限 80 MiB。
- 公网访问令牌有效期 5 分钟，刷新授权 30 天；权限撤销可能需等旧访问令牌过期。
- 实验室内网仍直接使用 CUPS，无逐人登录限制；靠固定 Pi 队列 UUID 探测，未读取 Wi-Fi SSID。
- 原 CUPS IPP 重复默认属性未根治，只在 Windows 桥输出中兼容过滤；稳定 DHCP 地址、protected print 和更多客户端仍待验收。
- DOCX 网页转换/字体与完整 CLI print/jobs 管理均未包含。

## 发布与回退

发布文件为 ICTHubPrinterSetup.exe 和 SHA256SUMS.txt。GitHub 标签构建先生成草稿，实际发布说明必须带上当时验收状态。生产部署从干净提交创建版本目录，失败恢复前一版本；原 P1 CUPS 备份继续保留。卸载器仅删除本应用拥有的打印队列、当前用户启动项与凭据，不删除原有 HP/WSD/USB 队列。
