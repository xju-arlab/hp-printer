# 打印机状态 API

`GET https://hp.icthub.top/v1/status`，公开只读 JSON，无需登录。不提供状态网页。

```bash
curl https://hp.icthub.top/v1/status
```

## 字段

| 字段 | 含义 |
|---|---|
| `schemaVersion` | 当前为 `1` |
| `printerName` / `model` | 打印机显示名、型号 |
| `online` | 本次采集是否能通过本机 ipp-usb 读取物理打印机；失败不能区分断电、断线或协议故障 |
| `state` | `idle`、`processing`、`stopped`、`unknown` |
| `stateLabel` | 对应中文说明 |
| `paperEmpty` / `paperLow` | 设备是否报告缺纸/纸张不足；不可读为 `null` |
| `paperLabel` | 缺纸、纸张不足、未报告缺纸或暂不可读。未报告缺纸不能证明纸盒里有纸 |
| `supplies` | 墨盒或其他耗材数组；设备不提供耗材数据时为空数组 |
| `supplies[].levelPercent` | 设备估计的 0–100 百分比；负数、不支持或未知均为 `null` |
| `supplies[].levelRaw` | 原始 IPP 整数；保留 -1/-2/-3，便于调用方区分设备报告 |
| `supplies[].name / type / color` | 耗材名称、类型和颜色；此机为彩色墨盒、黑色墨盒 |
| `supplies[].low / lowThresholdPercent` | 是否到设备自身低墨阈值和阈值百分比；未知为 `null` |
| `suppliesApproximate` | 为 `true`，百分比是设备估计值 |
| `checkedAt` | 最近尝试采集的 UTC 时间 |
| `observedAt` | 最近一次成功读取物理打印机的 UTC 时间，启动后从未成功时为 `null` |
| `stale` | 设备读取失败时为 `true`；此时保留的墨量是旧数据，调用方必须结合时间显示 |
| `refreshAfterSeconds` | 为 `15`；建议客户端每 15 秒或更慢刷新 |
| `device` / `queue` | 物理设备和 CUPS 队列各自的读数、来源时间、可达性、原始状态原因、接收任务开关和任务总数 |
| `paperReportsDiffer` | 设备和 CUPS 本次缺纸报告是否不同；任一不可读时为 `null` |

顶层纸张、状态和墨量以物理设备为来源，`source=device`。CUPS 有时保留旧原因，不能用它覆盖设备当前读数。设备不可达时，顶层状态为 `unknown`，纸张字段为 `null`；`device` 内可能保留上次值并标记 `stale=true`。

## 访问与负载

HTTP 200 表示 API 能返回结构化状态，不等于设备在线。网络失败要同时检查 HTTP 状态及 `online/stale`。响应允许 `Access-Control-Allow-Origin: *`，仅 GET，浏览器无需发送 Authorization 或额外请求头。

服务端按 15 秒缓存、合并并发采集，使用固定本机地址和 Get-Printer-Attributes。公开数据不包含文档名、用户、任务明细、序列号、设备 URL、令牌或管理操作。公网打印仍在 `/ipp/print` 校验账号授权。

来源定义：[CUPS marker 属性](https://openprinting.github.io/cups/doc/spec-ipp.html)、[PWG IPP 状态原因](https://www.pwg.org/ipp/ippguide.html)。
