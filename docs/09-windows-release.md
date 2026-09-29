# Windows 安装包与公网 IPP

本轮交付范围：Authenticator 邮箱验证与打印组准入、Windows 系统打印机、校外 HTTPS 打印、GitHub 私有 Release 和 Pi 同版本部署。DOCX 网页转换与上传页留在后续阶段。

## 数据路径

- 现有 CUPS/ipp-usb/USB 队列保持为唯一实际调度者。
- 安装器通过 Authentik Authorization Code + PKCE 在系统浏览器登录。固定 public client 不包含 client secret。邮件验证和 `hp-printer-users` 授权组两者都必须满足。
- Windows 使用内置 Microsoft IPP Class Driver，系统打印机命名为 `算法实验室·惠普打印机`。
- 当前 Windows 用户登录时启动 Python 后台 IPP 桥，监听 `127.0.0.1:18765`。登录令牌使用 Windows 当前用户 DPAPI 加密。
- 桥在能访问指定实验室 Pi 时优先直连 CUPS；校外通过 `https://hp.icthub.top/ipp/print`，Cloudflare Tunnel 转发到 Pi `127.0.0.1:8765`。IPP 基于 HTTP，因此本方案不再需要客户端 cloudflared 或新增 TCP Tunnel/Cloudflare Access 应用。
- 公网网关校验 Authentik 访问令牌，并限制到唯一队列和必要的 IPP 操作。禁止 Print-URI/Send-URI、CUPS 管理操作、访问其他用户的远程任务。
- 令牌到期由后台组件刷新；刷新授权失效需要重新登录。前台安装通过认证后才配置 Windows 打印机。
- 只读探测可以决定后续请求的路由。发送作业的请求失败后不自动换路重发；有 CUPS 作业 ID 的后续请求固定在原通道。

## 版本与部署

私有仓库 `xju-arlab/hp-printer` 是版本来源。本地修改提交后推送，Pi 使用只读 deploy key 拉取，拒绝覆盖远端工作区改动；不在 Pi 直接维护业务源码。生产服务使用锁文件安装依赖，发布记录 commit 和 tag。

Windows EXE 由版本化构建脚本生成；GitHub Release 附 EXE、SHA256 和版本说明。账号准入由 Authentik 和公网网关执行，不依赖下载链接保密。

## 验收约束

- 正常用户浏览器登录，未验证邮箱和无打印组用户均不能安装/使用公网服务。
- Windows 真实添加系统队列；至少一份合成文档经过公网 HTTPS 路径进入原 CUPS 队列。
- LAN 和强制公网测试分别记录，强制公网测试不等于实际在校外网络实测。
- 软件的 CUPS completed 与用户目视出纸分开记录。
- 本轮无需收集用户账号密码，不把 token、字体文件、打印文档或数据库提交到 Git。
