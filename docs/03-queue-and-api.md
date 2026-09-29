# 03 队列、数据与 API 详细设计

[返回主计划](README.md) · [架构](02-architecture.md)

本文为待实现契约。接口使用 `/api/v1`，不表示当前已运行 HTTP 服务。

## 1. 队列原则与模块接口

同一物理设备只接管 `HP_DeskJet_4900` 一条 CUPS 队列。Windows 原生任务直接进入 CUPS，必须与 API 任务一起被同步和管理。CUPS 已接收任务的输出不依赖管理服务在线。

`CupsAdapter` 暴露 `get_printer()`、`get_capabilities()`、`list_jobs()`、`get_job()`、`create_held_job()`、`send_document()`、`hold_job()`、`release_job()`、`cancel_job()`、`pause_printer()`、`resume_printer()`、`set_accepting()`。参数采用结构化值；队列来自部署配置白名单；异常转换为明确类型；不接收任意 shell、URI 或 CUPS 操作名。

本地 socket 优先。读权限和管理权限分别验证，不能因为进程加入某个 Linux 组就宣称已获得正确的 CUPS policy 权限。

## 2. 任务状态

保存原始 IPP 状态、原因和采样时间，CLI 提供中文解释与稳定 JSON 字段。IPP 操作与状态以 [CUPS IPP 说明](https://openprinting.github.io/cups/doc/spec-ipp.html) 为依据。

| IPP 值 | 原始状态 | 命令输出含义 | 可尝试的管理员操作 |
|---|---|---|---|
| 3 | pending | 排队中 | 挂起、取消 |
| 4 | pending-held | 已挂起/等待材料或认证等，结合 reasons | 可释放的任务恢复；取消 |
| 5 | processing | 正在处理/输出 | 取消；不承诺能在当前纸张中途停止 |
| 6 | processing-stopped | 处理中断 | 先处理原因；根据设备/队列状态恢复 |
| 7 | canceled | 已取消 | 终态，不直接恢复 |
| 8 | aborted | 已中止 | 终态；如需重打，显式创建新任务 |
| 9 | completed | 打印服务报告完成 | 终态；不等于人工确认所有纸张完整 |

同步失败用 `syncStatus=stale/unavailable` 表示，保留最后状态；不能伪造 IPP 的 failed 状态，也不能把空查询当作所有任务已完成。历史被 CUPS 清理后标记 `visibility=missing`，未获终态的任务进入 `completionConfidence=unknown`，不自动重打。

CLI/API 返回 `lastObservedAt`、原始原因及“状态暂不可用”。纸张卡住、缺纸、设备重启后的输出情况可能无法精确判定；没有可靠的物理页数反馈时，不实现“从第 N 页自动续打”。

## 3. 数据模型

SQLite 仅保存元数据、控制记录和提交意图，不复制 Windows 文档。时间全部存 UTC，UI 按用户时区显示。

| 表 | 主要字段与约束 |
|---|---|
| `printer` | 本地 UUID、逻辑名、CUPS server instance ID、queue name/UUID、backend URI 的受限摘要、能力 JSON、observed_at |
| `print_job` | 本地 UUID、printer_id、cups_job_id、cups_job_uuid（若有）、source、source_confidence、reported_user、authenticated_subject、title_redacted、IPP state/reasons、timestamps、sync_status、version |
| `submission` | UUID、认证主体、幂等键、请求摘要、状态、临时文件引用、关联 token、已知 CUPS job ID、失效时间；唯一 `(subject, idempotency_key)` |
| `control_operation` | UUID、actor、target、action、expected_version、requested_at、result、confirmed_at、sanitized_error |
| `audit_event` | actor、对象、事件类型、时间、前后状态摘要、request ID；不写文件内容、凭据、完整敏感标题 |
| `sync_checkpoint` | 队列标识、上次成功查询、事件序号/订阅期限（如启用）、同步租约 |

唯一任务映射为 `(server_instance_id, queue_uuid, cups_job_id)`；服务器实例 ID 是安装接管时生成并保留的本地标识。重装 CUPS、重建队列或任务 ID 回绕导致身份冲突时，先核对 UUID/创建时间，生成新实例代次，不覆盖旧历史。`cups_job_id` 不能独立作为长期全局标识。

外部任务先标 `source=ipp_external`，来源置信度 `unverified`，不能仅根据标题/用户名断言来自 Windows。经过本服务持久化提交映射的任务才标 `api` 或经过认证的 `labos`。

## 4. 对账与恢复

建议活跃任务每 2 秒同步、空闲每 10 秒同步；失败指数退避到 30 秒。该频率是起始参数，按 Pi 负载调整。P2 先用轮询做可靠全量对账，后续 IPP 订阅只作为刷新提示，通知丢失仍能恢复。

启动时读取所有未终结本地任务，拉取队列当前任务及有限历史，再逐一核对未知任务。只有单个同步 worker；多进程部署用 lease 防重复同步，但不能让 lease 过期导致重复提交打印。

更新和审计用短数据库事务。网络调用不占用长数据库写锁。API 返回查询时间和同步状态；分页使用稳定游标，默认只查活动任务，历史按时间范围查询。

## 5. API 提交与幂等

原生 Windows 流程沿用 CUPS 协议，不要求 Windows 经过上传 API。API 首版只接收 PDF 文件流；支持类型以文件内容验证，不只看扩展名；不接收任意远程下载 URL，不执行 Office 转 PDF。

建议 API 限制：每文件 50 MiB、1–20 份、A4、黑白/彩色、单面、固定优先级 50；打印范围和更多纸型后加。能力外参数明确返回 422，不静默忽略。全机 spool 容量和任务上限必须另在 CUPS 层限制，因为 API 限制管不到原生 Windows。

API 使用幂等键，范围为认证主体。请求摘要覆盖文件 hash 和规范化打印选项：相同键/相同摘要返回同一 submission；相同键/不同摘要返回 409。CLI 在发出请求前保存 request ID，并将其作为 Idempotency-Key；响应丢失后可按此键查询。服务端同步计算 hash，不相信客户端声明的摘要。

```text
RECEIVING → VALIDATED → CREATING_HELD → UPLOADING → READY_TO_RELEASE → LINKED
                              ↘ UNKNOWN_PENDING_RECONCILIATION
```

1. 流式落地到受限临时目录，限制大小、磁盘余量和验证资源；持久化提交意图及随机关联 token，再访问 CUPS。
2. `Create-Job` 先以 `job-hold-until=indefinite` 创建暂存作业，记录返回的 CUPS job ID。该技术挂起仅用于可靠接收，验证成功即自动释放，不是人工审批。
3. `Send-Document` 发送单个 PDF 并标记末文档；确认文档接收状态，提交数据库映射，再执行 `Release-Job` 自动进入排队。
4. 任一响应超时都先查询已有任务。创建响应丢失时，用已持久化的 token 和队列/时间/主体等交叉验证找回；不能只靠可被伪造的标题认领任意任务。
5. 文档上传响应丢失时，不盲目重发 `Send-Document`，以免产生第二份文档。能确认已接收才继续；无法确认保持挂起并报告待处理，必要时管理员取消该任务后明确重试。
6. 释放响应丢失时查询同一任务，不创建新任务。应用重启从提交意图恢复；已在处理或终态的任务不重复释放/重建。

`Create-Job`、文档数量查询、末文档处理与 hold/release 的实际行为先在 P4 验证；实现不得在这些能力尚不确定时偷偷降级成重复调用 `Print-Job`。超时暂存作业只能在确认尚未释放、由本服务创建且记录审计后清理；未知状态留给诊断。

这里保证可追踪的提交和不盲目重试，不宣称物理打印 exactly-once。断电、USB 传输与设备缓存仍可能让已输出页数不确定。

## 6. 管理操作语义

| 操作 | CUPS 行为 | CLI/API 说明 |
|---|---|---|
| 挂起任务 | Hold-Job | 对可挂起状态生效；处理中的任务不承诺立即冻结 |
| 恢复任务 | Release-Job | 释放可恢复的 held 任务；不用于 canceled/aborted |
| 取消任务 | Cancel-Job | 先显示取消请求中，查询确认终态；已输出的纸张无法撤回 |
| 暂停队列执行 | Pause-Printer/等效受限操作 | 保留队列，允许接收与否由另一开关控制；设备可能完成缓冲中的页 |
| 恢复队列执行 | Resume-Printer/等效操作 | 先检查停止原因；继续已有作业，避免自动创建副本 |
| 停止/恢复接收 | CUPS-Reject-Jobs / Accept-Jobs | 控制新任务；不是暂停现有打印 |

读改写控制采用 `expectedVersion`，状态变化时重新查询再操作；已达到目标状态可返回幂等成功。鉴权、操作意图持久化成功后才调用 CUPS；数据库无法记录审计时拒绝新的管理写操作。未知结果返回 operation ID，后台核验。普通请求不可执行 Purge-Jobs、重建队列或修改驱动。

## 7. HTTP 契约

| 方法与路径 | 请求/返回 | 权限 |
|---|---|---|
| `GET /health/live` | 进程存活，无内部配置 | 最小信息可公开给局域网监测 |
| `GET /health/ready` | DB、CUPS、同步器是否就绪；设备缺纸另报 degraded | 管理/监测身份 |
| `POST /api/v1/auth/sessions` | CLI 用户名/口令登录，返回有期限的 opaque bearer token；限速、禁止秘密日志 | 登录入口，仅环回或 HTTPS |
| `DELETE /api/v1/auth/sessions/current` | 撤销当前登录凭据 | 已登录身份 |
| `GET /api/v1/auth/me` | 当前主体、角色、scope、会话期限 | 已登录身份 |
| `GET /api/v1/printers` | 受管理打印机及采样时间 | 管理员/受限集成 |
| `GET /api/v1/printers/{id}/capabilities` | 支持选项、默认值、unknown 标记 | 管理员/受限集成 |
| `GET /api/v1/jobs?printerId=&state=&cursor=` | 分页投影与同步状态 | 管理员；集成仅自身可见记录 |
| `GET /api/v1/jobs/{id}` | 单任务、原始原因、可操作项 | 同上 |
| `POST /api/v1/submissions` | multipart PDF + options；`Idempotency-Key`；202 + submission ID | `jobs:submit` |
| `GET /api/v1/submissions/{id}` | 接收、对账、CUPS 关联与失败原因 | 提交者/管理员 |
| `GET /api/v1/submissions?requestId=` | 按当前主体的幂等键查找提交，响应丢失后的查询入口 | 提交者；不按自报用户名越权查找 |
| `POST /api/v1/jobs/{id}/actions` | `action=hold/release/cancel`、expectedVersion；202 + operation ID | 管理员；首版不支持自报用户名授权 |
| `POST /api/v1/printers/{id}/actions` | `pause/resume/accept/reject`、expectedVersion；202 + operation ID | 管理员 |
| `GET /api/v1/operations/{id}` | requested/confirmed/failed/unknown | 发起者/管理员 |
| `GET /api/v1/diagnostics` | 脱敏诊断摘要 | 管理员 |

错误结构固定为 `code/message/requestId/retryable/details`。分别使用 401/403、409 状态或幂等冲突、413 超限、415 类型错误、422 无效打印选项、429 提交节流、503 上游不可用、507 空间不足。`retryable=true` 仅表示适合以原幂等键重查/重试，不等于允许创建新任务。

队列响应至少含 `acceptingNewJobs`、`processingPaused`、`printerState`、`stateReasons`、`syncStatus`、`observedAt`；不能用单个 online 布尔值抹掉这些差异。

## 8. 管理认证

保留用户已确认的“管理员登录管理”，入口改为 CLI。通过受限本机 `auth init-admin` 初始化账户，口令用适合密码存储的哈希保存，禁止默认口令。`auth login` 在终端隐藏输入口令，换取有期限、可撤销的 bearer token；服务端只存令牌摘要，客户端保存在当前用户受限配置中。无需网页 session cookie 或浏览器登录流程。

管理 API 默认监听 `127.0.0.1:8765`，管理员可通过 SSH 到 Pi 操作 CLI；若开放 LAN API，使用 HTTPS 且验证证书。CLI 的打印/查询/控制按服务端 scope 检查；Windows LAN 原生打印仍不要求登录。集成使用独立的受限服务令牌，日志不输出令牌，CLI 不持有 CUPS 管理凭据。配置和输出约束见 [CLI 设计](08-cli-and-uv.md)。
