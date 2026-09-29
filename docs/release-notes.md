# ICTHub Printer 0.1.0

Windows 系统打印机安装程序，设备名：算法实验室·惠普打印机。

- 安装前通过系统浏览器登录 Authentik，要求邮箱已验证并具有 hp-printer-users 权限。
- 使用 Windows 自带 Microsoft IPP Class Driver；安装后台组件支持内网优先和公网 HTTPS 打印。
- 当前 Windows 用户登录后自动运行；授权失效时通过开始菜单重新登录。
- 本地凭据使用当前用户 DPAPI 加密；公网服务不接受匿名 IPP 提交。
- GitHub 私有仓库管理版本；Pi 从相同提交部署，保留现有 CUPS/USB 队列。

安装：下载 ICTHubPrinterSetup.exe，核对 SHA256SUMS.txt，双击运行。登录后在 Word 的 Ctrl+P 列表选择打印机。Windows 若要求管理员权限，按系统提示使用本机管理员完成。

当前安装包未使用商业代码签名证书。Windows 可能显示未知发布者或 SmartScreen 提示。仅从本私有仓库下载。

本版每次 IPP 请求最大 80 MiB；后台组件随安装用户登录启动。已提交请求超时不会自动换通道重发；请先检查队列。DOCX 上传/服务器转换不在此版范围。

具体验收结果和已知限制以 docs/verification/windows-release-20260929.md 为准。
