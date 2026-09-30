# ICTHub Printer v0.1.0-rc.2

Windows 打印机名称：**算法实验室·惠普打印机**。请使用 RC2；RC1 存在已修复的登录验证与 Windows 接入问题。

## 已完成

- winbeau 通过真实浏览器 PKCE 登录，邮箱和打印组准入通过；凭据由当前用户 DPAPI 加密保存。
- Windows EXE 安装成功，使用系统 Microsoft IPP Class Driver；配置当前用户启动项、开始菜单和卸载入口。
- Windows 系统打印接口经公网 HTTPS 成功提交一页合成文档：Windows job 5 → CUPS job 4，CUPS 状态 completed；用户已确认测试页很快出纸。
- 实验室网络强制公网路径已验证；测试后恢复内网优先。真实授权刷新、后台从启动项恢复和 LAN 查询均通过。
- 修复 Cloudflare JWKS 403、队列配置所需 UAC、Windows IPP URI 小写，以及中文设置文件编码问题。
- 40 项自动检查通过。原 CUPS/USB 配置、旧 Windows 队列和 USB 默认打印机保留。

## 使用

下载 ICTHubPrinterSetup.exe，核对 SHA256SUMS.txt，双击安装。使用已获打印授权的 ICTHub 账号登录；Windows 请求添加打印机权限时选择“是”。在 Word 的 Ctrl+P 中选择“算法实验室·惠普打印机”。有效登录可以复用，过期授权可从开始菜单重新登录。

## 尚待验收

**本轮 Word 自动化未完成，因此 Word 实际文档打印仍需人工验收。** 用户已确认公网测试页很快出纸，中文与字体细节未单独确认。实际校外网络仍待测试。

安装包未签名，Windows 可能提示未知发布者。后台随安装用户登录运行，单次 IPP 请求最多 80 MiB；请求结果不明时不会自动换通道重发。

网页上传、DOCX 服务端转换/字体部署和完整 CLI print/jobs 管理不在本版范围。详细证据见 docs/verification/windows-rc2-20260930.md。
