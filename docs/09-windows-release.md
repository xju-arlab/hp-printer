# Windows 安装包与公网 IPP

本轮交付范围：C# WPF 图形安装器、Authentik 窗口内登录、Windows 系统打印机、HTTPS 公网打印、GitHub/GitCode 公开 Release 和 Pi 同版本部署。新增公开只读 [状态 API](10-status-api.md)，不做状态网页。DOCX 网页转换与上传页留在后续阶段。

## 新用户注册

RC9 的首页和登录页提供“注册账号”。在安装器中填写用户名、邮箱、密码和确认密码，点击邮件中的验证链接后，返回安装器点击“已验证，登录”。新账号无需管理员逐个审批；该按钮仍执行正常登录与打印准入检查。

注册使用 Authentik 既有公共 Flow，账号资料由账号服务保存；安装器不使用管理 API。注册错误保留输入，进入邮件验证阶段后清空密码。邮件可以手动重发，客户端间隔至少 60 秒。完整注册与邮件验收尚未实测，见 [RC9 记录](verification/windows-rc9-20260930.md)。

## 数据路径

- 现有 CUPS/ipp-usb/USB 队列保持为唯一实际调度者。
- RC3 图形安装器通过 Authentik Flow Executor 在窗口内执行账号密码、动态验证码/恢复码和授权，继续使用 Authorization Code + PKCE、state、nonce。固定 public client 不包含 client secret。已激活、已验证邮箱的账号自动获得打印 claim。CLI 旧浏览器登录入口保留兼容。
- Windows 使用内置 Microsoft IPP Class Driver，系统打印机命名为 `算法实验室·惠普打印机`。
- 当前 Windows 用户登录时启动 Python 后台 IPP 桥，监听 `127.0.0.1:18765`。登录令牌使用 Windows 当前用户 DPAPI 加密。
- 桥在能访问指定实验室 Pi 时优先直连 CUPS；校外通过 `https://hp.icthub.top/ipp/print`，Cloudflare Tunnel 转发到 Pi `127.0.0.1:8765`。IPP 基于 HTTP，因此本方案不再需要客户端 cloudflared 或新增 TCP Tunnel/Cloudflare Access 应用。
- 公网网关校验 Authentik 访问令牌，并限制到唯一队列和必要的 IPP 操作。禁止 Print-URI/Send-URI、CUPS 管理操作、访问其他用户的远程任务。
- 令牌到期由后台组件刷新；刷新授权失效需要重新登录。前台安装通过认证后才配置 Windows 打印机。
- 只读探测可以决定后续请求的路由。发送作业的请求失败后不自动换路重发；有 CUPS 作业 ID 的后续请求固定在原通道。

## 版本与部署

GitHub 公开仓库 `xju-arlab/hp-printer` 是版本来源，GitCode 同名组织和仓库同步 main、标签与当前 Release。下载无需登录代码托管平台；所有已激活且已验证邮箱的 ICTHub 账号均可使用打印，实验室内网继续直接打印。本地修改提交后推送两端，Pi 拉取同一提交，拒绝覆盖远端工作区改动；不在 Pi 直接维护业务源码。生产服务使用锁文件安装依赖，发布记录 commit 和 tag。

组织禁止 deploy keys；首次 SSH 代理转发也因本机 SSH key 没有 GitHub 权限而失败。最终同步脚本使用本机现有 `gh` 登录，通过 SSH 标准输入临时提供 GitHub 授权。授权只存在同步进程内存和子进程环境中，不写入 Pi 配置、URL、文件或日志，GitHub 请求仅发向 `github.com`。拉取通过本机 LAN HTTP 代理 `192.168.5.71:10808`，因此同步时电脑需要在线并开放此代理；已部署打印服务独立运行。

本地日常步骤：

```bash
git add <本轮文件>
git commit -m "描述变更"
git push origin main
git push gitcode main --follow-tags
bash scripts/sync-pi.sh
```

随后在 Pi 执行 `sudo bash /home/winbeau/xju-arlab/hp-printer/scripts/install-pi.sh`。如果 uv 下载也需要代理，使用 `sudo env HTTPS_PROXY=http://192.168.5.71:10808 HTTP_PROXY=http://192.168.5.71:10808 bash ...`。服务从 `/opt/hp-printer/releases/<commit>` 运行，切换失败会恢复前一个 release。

Authentik 使用本仓库的 `deploy/authentik-hp-printer.yaml`。应用/组/Provider 已独立于 auth-login 的静态前端代码；配置作为 database-backed BlueprintInstance 持久化，容器重建不依赖临时文件。注册入口保持开放；用户完成邮箱验证并激活后即满足 `studio-users` 基线。打印专属 groups scope 自动为此类账号签发 `hp-printer-users` claim，以兼容现有 RC2；不修改账号的全局组、不授予其他产品或管理员权限。管理员可停用或删除账号。访问令牌 5 分钟、刷新授权 30 天；停用或删除账号后，已签发的短期访问令牌可能继续有效至到期（网关另有 20 秒时钟容差）。

Windows 后台属于安装用户，使用开始菜单图形登录入口恢复过期授权。IPv4 loopback 18765 为打印桥；GUI 原生登录直接处理严格匹配的回调 URL，不监听 18766，旧 CLI 浏览器登录仍会监听它。后台不接收浏览器跨域请求。公网不开放 CUPS `/admin`；CUPS 本身的原始 P1 IPP 重复属性仍待修复，桥只对输出给 Windows 的重复默认值做兼容处理。

Windows EXE 由版本化构建脚本生成：先 PyInstaller 打包 Python 后台，再使用 .NET 9 SDK 将后台嵌入 WPF 自包含单文件。用户无需另装运行时。GitHub 和 GitCode Release 附同一份 EXE、SHA256 和简短说明。最新客户端 RC9 继续标记为候选版，验收边界见 [RC9 记录](verification/windows-rc9-20260930.md)；Pi 生产固定 RC3。

### 同步 Release

本地 `origin` 指向 GitHub，`gitcode` 指向 `https://gitcode.com/xju-arlab/hp-printer.git`。新环境先添加该 remote，并分别登录 `gh` 与 `gc`。现有 Windows 流水线仍只在 GitHub 构建；审核草稿并发布后，下载该版本的 EXE、SHA256 和发布说明，再用 `gc release create <tag> -R xju-arlab/hp-printer --prerelease --notes-file <说明文件>` 创建同名候选版，以 `gc release upload <tag> <EXE> <SHA256文件> -R xju-arlab/hp-printer` 上传原文件。发布前先推送同一标签，完成后比对下载文件的 SHA256。不要为镜像重建 EXE 或移动已有标签。

仓库同步和 Release 附件同步是两个步骤；当前通过维护者本机工具执行，尚未配置跨平台自动发布工作流。

## 验收约束

- 已激活且已验证邮箱的正常用户登录即可使用；未验证邮箱或已停用的用户不获得新的打印授权。
- Windows 真实添加系统队列；至少一份合成文档经过公网 HTTPS 路径进入原 CUPS 队列。
- LAN 和强制公网测试分别记录，强制公网测试不等于实际在校外网络实测。
- 软件的 CUPS completed 与用户目视出纸分开记录。
- 本轮无需收集用户账号密码，不把 token、字体文件、打印文档或数据库提交到 Git。
