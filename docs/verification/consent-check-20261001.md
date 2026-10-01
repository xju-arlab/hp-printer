# 授权页问题核查

检查时间：2026-10-01 UTC。用户提供“授权打印”页截图，权限说明为英文，红字为“账号要求的验证步骤暂不受安装器支持，请联系管理员。”。截图对应的客户端版本、账号与时间均未知。

## 版本与结论

当前正式版仍为 `v0.1.0`，提交 `ffc7348602a93ebfeb5c6c12be6b0f7194b19de1`，安装包 SHA256 `cdedd57a480605d4cb565e99cad01e4535baf485f4c899d153e20e185cfe5e5f`。main 与该标签的 `native_auth.py` 和 `MainWindow.xaml.cs` 没有差异。

- 英文说明问题确定仍存在：`NativeLogin.public_challenge()` 原样输出 `permissions` 和 `additional_permissions` 的 `name`，WPF 再逐行显示。其内容与截图中的内部 Scope 说明一致。
- 通用红字确定仍存在：未识别的组件统一落到同一条错误，包括 `ak-stage-autosubmit`、`ak-stage-flow-error`、`xak-flow-shell`。服务端错误会被归为“验证步骤不支持”，仅凭这条提示无法区分原因。
- 这不能证明截图中的授权失败必然在当前版复现。正常的 HTTP 302 与 `xak-flow-redirect` 完成路径通过了隔离模拟检查；真实截图对应的返回组件没有取到。
- 本轮为核查，没有修改认证代码、账号策略或发布新安装包；尚不能标记为已修复。

## 检查证据

1. 使用当前源码与 HTTPX MockTransport 构造合成授权挑战，检查授权 token 提交、HTTP 302 / JSON 重定向、state 匹配、令牌交换调用。令牌内容及 TokenVerifier 为模拟值，没有请求真实用户登录、发放授权或提交打印。两条正常完成路径均通过。
2. 将上述三种组件传给当前处理函数，均得到与截图完全相同的通用红字；合成权限列表中的英文名称原样保留。
3. 只读查询 huawei2：生产 Authentik 为 `2026.5.5`，打印 Provider 使用 `default-provider-authorization-explicit-consent`，显式配置的 Stage 为单个 Consent。按该 Flow 路径/打印应用关键字过滤最近两天最多 100 条系统、配置、策略异常，未匹配到记录。该有限查询不能排除历史异常或未入库的客户端错误。
4. 检查脚本位于本地忽略目录 `.runtime/check_current_consent.py` 和 `.runtime/inspect_consent_server.py`。输出不含密码、真实 OAuth code、cookie、token 或用户资料。

协议依据：[生产对应版本的 OAuth 完成阶段](https://github.com/goauthentik/authentik/blob/version/2026.5.5/authentik/providers/oauth2/views/authorize.py)、[挑战类型定义](https://github.com/goauthentik/authentik/blob/version/2026.5.5/authentik/flows/challenge.py)。Auth Code 默认使用 query 回调；form_post 对应 Autosubmit，不能仅凭截图认定它就是此次根因。

## 后续定位

授权文案可按已知 Scope ID 提供简短中文说明；需保留用户能理解的权限含义。错误处理应区分服务端错误和未支持的挑战，并仅保留经过校验的组件名/请求编号作为诊断信息。若后续复现，先取得返回组件及请求编号，再补兼容与回归用例；不因这条通用提示直接放宽登录、回调来源或邮箱准入检查。
