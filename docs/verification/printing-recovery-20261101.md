# 2026-11-01 外网打印恢复

## 故障证据

- Mac 0.2.0 打印后台正在运行，作业 27 等待远端；公网 `/health`、`/v1/status` 返回 HTTP 530 / Cloudflare 1033。
- 接入实验室内网后验证 `192.168.5.87` 的 CUPS UUID 与配置一致，并登录主机 `fourb`。树莓派已连续运行 9 天，打印网关、CUPS、ipp-usb 均在运行。
- cloudflared 2026.9.3 在约 10:59–11:02 UTC 反复出现 QUIC timeout / context deadline exceeded，四条连接均受影响；11:04–11:05 UTC 自动重连。这解释了先前的 1033，但日志不能单独确定上游网络丢包的具体原因。
- 公网恢复后，Mac 作业仍因 `cups-held-for-authentication` 挂起。通过已安装的 ICTHub Printer 完成账号重新登录及钥匙串交互。

## 部署修复

在同一树莓派、同一 tunnel 上临时运行 HTTP/2 连接验证，四条连接全部注册成功，再将本仓库 `deploy/cloudflared-http2.conf` 的环境变量配置写入：

`/etc/systemd/system/cloudflared.service.d/20-http2.conf`

执行 daemon-reload 并重启 cloudflared；生产服务在 11:21:58 UTC 恢复 active，四条连接均为 HTTP/2。原 unit 备份于 `/var/backups/hp-printer/20261101-tunnel/cloudflared.service`。临时验证服务 `hp-printer-tunnel-check` 已停止。

只更换 tunnel 的传输协议，保留 token-file、远端 ingress、账号准入与 TLS 校验。未改 CUPS/USB 配置、未更换已发布安装包。HTTP/2 配置会随 systemd 服务重启继续生效；这能避开本次 QUIC 故障路径，但不保证实验室网络永不掉线。

Cloudflare 参数依据：[Tunnel run parameters](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/run-parameters/)。

## 验证

- 生产 `/ready` 返回 200、`readyConnections: 4`；公网 `/health` 和 `/v1/status` 返回 200。
- 在 Mac 临时启用 `remote_only`，经现有打印后台发起 IPP 查询：HTTP 200、IPP status 0、route remote、loginRequired false。
- 恢复已有作业 27（没有新建重复作业），观察其从 processing 到 completed（IPP job-state 9）。随后恢复原有内网/公网自动选择设置。
- Mac 活动作业队列为空；设备与树莓派队列为 idle，未报告缺纸。实体纸张由用户目视确认，软件状态不代替纸张验收。

## 回退

将 `/etc/systemd/system/cloudflared.service.d/20-http2.conf` 移到上述备份目录，执行 `sudo systemctl daemon-reload` 和 `sudo systemctl restart cloudflared`，即可恢复原来的自动传输协议选择。不得删除 tunnel token 或更改 ingress 以回退此配置。
