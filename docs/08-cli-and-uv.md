# 08 CLI 命令与 uv 工程详细设计

[返回主计划](README.md) · [队列与 API](03-queue-and-api.md) · [实施阶段](06-roadmap-and-acceptance.md)

> 本文主要是后续 CLI 契约。当前已有 pyproject.toml、uv.lock、Python 3.12 包、help/version、doctor 和 serve；文件打印、队列管理及下述统一 JSON/退出码契约尚未实现。Windows 与公网优先范围见 [09](09-windows-release.md)。

2026-09-30 用户追加 Windows C# WPF 图形安装器，位于 `windows/ICTHubPrinter.Setup`。这不改变本章 Python + uv 后端与 CLI 布局。另有公开只读 [状态 API](10-status-api.md)。

## 当前可执行入口

```bash
uv sync --locked
uv run hp-printer --help
uv run hp-printer --version
# Pi 上只读检查现有 CUPS
uv run hp-printer doctor
uv run hp-printer serve --config config.example.toml
```

当前通过 HTTPX 直接处理受限 IPP，不依赖 pycups，不存在 `server` extra；构建使用固定的 hatchling。下面涉及 pycups、全局配置、管理员认证和 print/jobs 的章节保留为后续设计，不能当作当前命令使用。

## 1. 工程约定

用户指定 **纯 Python 后端 + uv + CLI 打印**。根目录就是 Python 工程，不再分 frontend/backend，不实现管理网页。Python 分发名为 `hp-printer`，导入包为 `hp_printer`，使用 `src/hp_printer/` 布局。

P2 建立 `pyproject.toml`、`.python-version`、`uv.lock`、包源码和必要测试。Python 首版验证范围为 3.12，建议 `requires-python = ">=3.12,<3.13"`、`.python-version` 写 3.12；扩版本时再验证原生扩展。

建议 CLI 使用 Typer，HTTP 客户端使用 HTTPX，服务使用 FastAPI，设备适配使用 pycups。入口字段如下；这不是完整的 pyproject 文件：

```toml
[project.scripts]
hp-printer = "hp_printer.cli:app"
```

必须配置真正的 `[build-system]` 和包发现规则，使安装后的 console script 可用，而不是只能从源码目录启动。构建后端及版本在 P2 选择并验证。[uv 项目配置](https://docs.astral.sh/uv/concepts/projects/config/)

## 2. 依赖和平台边界

| 层 | 依赖/用途 | 安装策略 |
|---|---|---|
| 默认依赖 | CLI、HTTP client、配置/校验 | 供 CLI 使用，不依赖 libcups |
| `server` extra | FastAPI、ASGI server、pycups 等服务依赖 | Pi/WSL Linux 使用；真实 CUPS adapter 仅支持经验证的 Linux 环境 |
| `dev` group | pytest、静态检查等 | 开发与 CI 使用，生产排除 |
| OS 包 | CUPS、ipp-usb、libcups；需要时加编译器和 Python headers | 由系统包管理器和部署预检处理，不由 uv 管理 USB 驱动 |

pycups 是 libcups 绑定；其原生构建和系统库在 Pi 上验证，不能把 `apt install python3-cups` 当作 uv 虚拟环境已可 import cups 的证据。[OpenPrinting pycups](https://github.com/OpenPrinting/pycups)

建议将 pycups 放入 server extra 并设置 Linux 平台标记，CLI 模块不在顶层 import cups。这样普通 CLI 的 `--help`、远程请求和 fixture 测试不要求本机有 CUPS；在不支持的系统执行 `serve` 必须清楚报错。Windows 原生打印不依赖 Python/uv；Windows Python CLI 是可单独验证的附加能力。

uv.lock 纳入版本管理，`.venv/`、本地凭据、上传文件、数据库、构建缓存不入库。默认依赖、extras、开发组分别声明；更新依赖时明确更新锁文件并运行对应测试。[uv 依赖管理](https://docs.astral.sh/uv/concepts/projects/dependencies/)

## 3. 开发、检查和部署命令

以下命令在 P2 创建工程后才可用：

```bash
# 普通 CLI 环境
uv sync --locked
uv run --locked hp-printer --help

# Pi / Linux 服务开发环境
uv sync --locked --extra server
uv run --locked --extra server hp-printer --config ./config.local.toml serve

# 开发检查和构建
uv lock --check
uv run --locked pytest
uv run --locked ruff check .
uv build

# 生产部署准备，在最终 release 目录执行
uv sync --locked --no-dev --extra server --no-editable
```

首次生成锁文件、选择 build backend 和添加依赖属于 P2 实现步骤；`--locked` 在元数据与锁文件不一致时失败，不自动更新锁文件。[uv 锁定与同步](https://docs.astral.sh/uv/concepts/projects/sync/)

生产环境由 systemd 直接执行最终版本目录内的 `.venv/bin/hp-printer --config /etc/hp-printer/config.toml serve`。启动不自动更新依赖或下载 Python。虚拟环境在目标 Linux 目录原地构建，不从 Windows 或其他路径复制；系统解释器和 headers 必须与构建目标一致。部署记录 uv、Python、libcups 和包版本；构建后端/构建依赖另固定并验证，不能认为 uv.lock 已自动锁定所有系统和隔离构建工具。

## 4. CLI 与常驻服务的关系

`serve` 运行 API 和唯一任务同步器。其他业务命令是该服务的 HTTP 客户端，默认地址 `http://127.0.0.1:8765`；管理员首版可 SSH 到 Pi 执行命令。

CLI 不直接打印到 USB，不自行打开服务端 SQLite，不在后端不可用时自动降级为 `lp` 命令。服务离线时返回明确错误；已经进入 CUPS 的任务继续由 CUPS 处理。配置检查、`--help`、`--version` 等离线命令无需服务运行；`auth init-admin` 是受限的本机维护命令，不能被远程 API 调用。

启动或连接服务的过程不会触发打印。真正输出纸张的入口为明确的 `print` 命令，测试工具 `doctor` 默认只读。CLI/API 首版文件格式为 PDF，原生 Windows 仍可通过应用自己的驱动转换打印 Word 等文件。

## 5. 命令契约

全局选项放在子命令之前：`--server`、`--config`、`--json`、`--request-timeout`。具体打印选项放在 `print` 后；配置优先级为命令参数 > HP_PRINTER 前缀环境变量 > 用户配置 > 默认值。令牌不提供明文 `--token` 参数，使用受限凭据文件或环境/标准输入。

| 命令 | 行为 |
|---|---|
| `hp-printer --help / --version` | 离线查看帮助/版本，不探测或打印 |
| `hp-printer --config PATH serve` | 常驻管理服务；默认仅环回地址，不隐式启用 LAN 共享 |
| `hp-printer auth init-admin` | 本机首次建立管理员，隐藏口令输入；已有管理员时拒绝重置 |
| `hp-printer auth login --username NAME` | 终端隐藏口令输入，获取有期限的管理凭据 |
| `hp-printer auth status / logout` | 查询登录状态/撤销当前会话并删除本机凭据 |
| `hp-printer printers list` | 列出服务已接管的打印机；不自动接管新设备 |
| `hp-printer printer status / capabilities --printer NAME` | 状态、接受/暂停、同步时间和能力 |
| `hp-printer print FILE.pdf --printer NAME` | 上传本机文件流，按统一提交契约入队；服务读取内容，不读取客户端路径 |
| `hp-printer submissions show --request-id UUID` | 按当前身份的幂等键核对已提交请求；响应丢失后首先使用此命令 |
| `hp-printer jobs list --printer NAME` | 默认活动任务；`--history`、分页用于历史 |
| `hp-printer jobs show JOB_ID` | 查看服务任务 UUID 对应的状态、CUPS ID、原因和来源置信度 |
| `hp-printer jobs cancel / hold / release JOB_ID` | 管理员操作；禁止将 canceled/aborted 任务当作可恢复 |
| `hp-printer operations show OPERATION_ID` | 查询管理动作是否确认，区分已请求与已生效 |
| `hp-printer printer pause / resume --printer NAME` | 暂停/恢复实际执行 |
| `hp-printer printer reject / accept --printer NAME` | 停止/恢复接收新任务，独立于暂停执行 |
| `hp-printer doctor` | 只读诊断；JSON 可供脚本处理，不发送测试页 |

除 `init-admin` 外，所有业务写操作经服务端授权、审计和控制契约。`init-admin` 仅在持有服务数据库/配置的本机维护权限、完成数据库迁移且无既有账户时使用，不提供任意修改数据库命令。

## 6. 文件打印与重试

计划示例，尚未实现：

```bash
uv run hp-printer auth login --username admin
uv run hp-printer print ./report.pdf --printer HP_DeskJet_4900 --copies 2 --color monochrome --paper A4
uv run hp-printer --json jobs list --printer HP_DeskJet_4900
uv run hp-printer printer pause --printer HP_DeskJet_4900
uv run hp-printer printer resume --printer HP_DeskJet_4900
```

打印选项首版包括 `--copies 1..20`、`--color monochrome|color`、`--paper A4`、`--sides one-sided`、`--request-id UUID`、`--wait`、`--wait-timeout SECONDS`。默认值通过服务能力获取，参数两端校验；超过能力不静默纠正。批量目录、远程 URL、Office 转换和自动双面暂不包含。

每次新打印意图在网络请求之前生成并持久化 request ID、目标服务/身份、文件 hash 和选项摘要；元数据文件失败就不提交。提供 `--request-id` 可显式继续同一次请求；不能按文件名自动去重，也不能把一次新意图误当成重试。

请求正文开始发送后连接断开，CLI 返回“结果待核验”和 request ID，先按键查询，再决定是否以**同一幂等键和同一文件/选项**重试。CLI 中断或机器重启后能从受限本机记录找回 request ID；服务端沿用持久化提交意图和 CUPS 对账，绝不偷偷创建另一份任务。第二次裸运行 `print` 属于新打印意图，会使用新键，应在帮助文档写清楚。

默认打印命令返回服务接收回执，输出 `acceptedBy=service`、submission ID、request ID、当前状态及已知 CUPS ID；仅当已获得 CUPS ID 才表述“已进入 CUPS”。退出码 0 不意味着纸张已经输出。

`--wait` 等待原任务终态，成功也仅表示 CUPS 报告 completed。等待超时或 Ctrl+C 只结束客户端等待，不取消或重提任务；提示查询命令和 request ID。取消需显式执行 `jobs cancel`。

## 7. 输出、退出码和认证

普通模式打印简洁表格/说明；`--json` 模式 stdout 只含一个完整 JSON 对象，日志/进度写 stderr。输出包含 `schemaVersion`、`status`、`data`、`error`、`requestId`；参数解析错误也应统一为可机器识别的输出，不夹杂彩色提示和进度条。文件正文、密码、令牌不进入输出。

| 退出码 | 含义 |
|---|---|
| 0 | 命令已成功完成约定动作；提交回执不是物理出纸证明 |
| 1 | 未分类本地/服务内部错误；结合稳定 error.code |
| 2 | 参数、配置、文件类型或打印选项错误 |
| 3 | 未登录、凭据失效或权限不足 |
| 4 | 连接/服务不可用，能确定尚未接收提交；否则使用 6 |
| 5 | 状态冲突或幂等键与文件/选项冲突 |
| 6 | 提交或控制结果未知，必须查询/对账；不能自动新建任务 |
| 7 | 等待到 canceled/aborted 或确认的执行失败 |
| 8 | 等待超时但原任务仍存在，不表示已取消 |
| 130 | 用户中断等待/传输；传输中断需按回执/键核对结果 |

认证沿用“管理员登录管理”。CLI 只通过终端隐藏输入或显式标准输入获取口令，不支持口令命令参数；登录会话有期限、可撤销。用户凭据文件在 Linux 为 0600、目录 0700，Windows 若支持则设置当前用户 ACL；无法建立合适权限时拒绝保存明文令牌。禁止以提交者自报用户名获得管理权限。

本机环回 HTTP 配合既有 SSH 使用；非环回地址要求 HTTPS 和证书校验，不提供默认跳过验证。CLI 权限控制不改变 Windows 原生 LAN 打印无需逐人认证的既定需求。

## 8. 验收重点

P2 提供帮助/版本、服务启动和只读查询；P3 提供登录与管理命令；P4 提供 `print` 和幂等恢复；P5 完成稳定 CLI、脚本输出、打包与联调。

需要测试：包安装后从非源码目录执行、默认依赖不导入 cups、路径含空格/中文、文件超限、能力不支持、过期凭据、stdout JSON 纯净、明确退出码、请求/响应丢失、等待中断不取消任务。Pi 实机 CLI 与 Windows 原生任务必须进入同一队列；fixture 测试不能替代真实出纸记录。
