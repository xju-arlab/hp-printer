# 开放打印准入记录

日期：2026-09-30。用户要求开放注册，取消打印服务的逐人审批。

## 原因与变更

- Authentik 生产环境的 `ICTHUB_REGISTRATION_ENABLED` 与 `ICTHUB_ACCOUNT_ID_ALLOCATOR_READY` 均已为 `true`，公共注册本身已开放。
- 反馈账号已激活、有邮箱且属于邮箱验证完成后加入的 `studio-users`，但没有人工加入 `hp-printer-users`，因此被打印应用策略拒绝。
- 已将打印应用策略改为允许所有已激活、有邮箱且通过上述邮箱验证基线的账号。
- 增加仅用于打印 Provider 的 `ICTHub HP Printer verified account groups` scope mapping，为符合条件的账号自动签发兼容 RC2 的 `hp-printer-users` claim。全局组成员关系、其他应用策略、邮箱验证流程均未修改。

## 部署证据

- 配置提交：`04df7d22ab10ac65c70fa8691b47c5c3cbbd9091`；由 huawei2 从 GitHub 拉取已提交的 Blueprint。
- Blueprint SHA256：`327e06e9758a6e76961d29bac6697a9a88ed49f6de460b7f9fdd25a41a47c579`，与本地文件一致。
- Authentik `apply_blueprint` 成功；读回确认应用策略移除了人工打印组条件，Provider 使用打印专属 groups mapping。
- 已更新 worker 中的 Blueprint 文件，以及数据库中的 `ICTHub HP Printer (xju-arlab/hp-printer)` BlueprintInstance，防止旧配置恢复限制。
- 变更前后配置备份在 huawei2 的 `/home/winbeau/hp-printer-auth-backups/open-20260930/`。
- 本轮未重建安装包、未重新部署 Pi 服务、未打印文件；现有 RC2 可继续使用。反馈账号的新浏览器登录结果由用户重试确认。

管理员可以停用或删除账号以收回后续登录与刷新权限。已经签发的访问令牌有效期为 5 分钟，网关另允许 20 秒时钟容差。

回退时应用备份 `before.yaml`，并同步恢复上述数据库 BlueprintInstance 的内容；仅恢复文件会与数据库声明冲突。
