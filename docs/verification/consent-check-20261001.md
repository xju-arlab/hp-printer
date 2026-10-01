# 授权页问题核查与修复

检查时间：2026-10-01 UTC。用户反馈正式版仍在“授权打印”页报“账号要求的验证步骤暂不受安装器支持”。

## 根因

已根据用户指定账号只读核对生产 Authentik 2026.5.5 的事件、会话状态和服务日志：

- 账号已激活，满足现有邮箱和用户组准入要求，密码登录成功。
- 正式版 `ICTHubPrinter/0.1.0` 的两次失败分别发生在 04:47:59、04:49:08 UTC；RC9 也有相同记录。会话停在 Consent，OAuth 使用 code/query，未完成打印应用授权。
- 对应服务日志明确为 `PermissionDenied('CSRF Failed: CSRF token missing.')`，发生于 `default-provider-authorization-explicit-consent`。
- 服务端配置为 Cookie `authentik_csrf`、请求头 `X-Authentik-CSRF`。安装器却使用 `X-CSRFToken`。匿名登录阶段未暴露该问题，已登录会话提交授权时被拒绝；服务端将异常包装为 `ak-stage-flow-error`，旧客户端再误报为不支持验证步骤。

这也解释了此前只模拟正常 302 / JSON 跳转的检查为何没有发现问题：模拟服务没有检查 Authentik 的专用 CSRF 请求头。该次早期核查未取得账号线索，不能作为真实授权成功证据。

协议依据：[生产对应版本的 CSRF 配置](https://github.com/goauthentik/authentik/blob/version/2026.5.5/authentik/root/settings.py)、[Flow 异常响应](https://github.com/goauthentik/authentik/blob/version/2026.5.5/authentik/flows/views/executor.py)。

## v0.1.1 修复

- 登录与注册共用 `X-Authentik-CSRF` 请求头，每次提交读取当前 Cookie；仅在已登录的授权步骤缺少 Cookie 时提示重新登录。匿名登录/注册允许服务器尚未下发 Cookie，服务器的认证与 CSRF 校验继续执行。
- 服务端流程错误改为准确提示，仅在格式合法时显示请求编号；不显示服务端错误正文、用户资料或堆栈。
- 已知授权 Scope 改为简短中文，去掉空行和重复项；未知权限仍显示服务端说明，避免隐藏新增权限。
- 未修改生产账号、认证策略、CSRF 防护、邮箱/MFA 校验或打印权限。

## 检查证据与边界

1. 在生产容器内，使用 RequestFactory 与合成 Cookie 调用现有 CSRFCheck，未发送真实用户请求：旧请求头返回 `CSRF token missing.`，新请求头通过。没有写入账号、会话或授权。
2. 新增 15 项隔离检查：CSRF Cookie 轮换后授权完成、HTTP/JSON 回调、各登录步骤、注册提交、缺失 Cookie、中文权限、服务错误隐私过滤与授权重试提示。所有请求通过 MockTransport，未登录真人账号或提交打印。
3. 全部 55 项检查及 Ruff 通过。PKCE、state、nonce 和令牌校验继续保留。
4. 公网匿名访问登录与注册入口均返回正确表单；确认此时服务器仅下发匿名 session，尚未下发 CSRF Cookie，增加对应的无 Cookie 提交用例。首轮尚未发布的构建因此取消，完成修正后重新构建。
5. 真实 Windows 安装器登录、点击“允许”及后续打印仍待用户重试；不能将隔离检查写成真实账号验收。

构建和发布信息将记录在下方。诊断脚本保存在忽略目录 `.runtime/`，公开仓库不收录用户账号、邮箱、Cookie、OAuth code 或令牌。
