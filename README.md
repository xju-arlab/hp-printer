# hp-printer

[![Release](https://img.shields.io/github/v/release/xju-arlab/hp-printer?style=flat-square&logo=github&label=release)](https://github.com/xju-arlab/hp-printer/releases/latest)
[![Checks](https://github.com/xju-arlab/hp-printer/actions/workflows/checks.yml/badge.svg?branch=main)](https://github.com/xju-arlab/hp-printer/actions/workflows/checks.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-C%23%20WPF-0078D4?style=flat-square)

**算法与科研实验室打印服务**。树莓派 4B 通过 USB 连接 HP DeskJet 4900，为 Windows 提供内网与公网打印。

## 下载与使用

**[GitHub 下载](https://github.com/xju-arlab/hp-printer/releases/latest) · [GitCode 镜像](https://gitcode.com/xju-arlab/hp-printer/releases)**

1. 下载并运行 `ICTHubPrinterSetup.exe`。
2. 登录账号并安装；新用户可在安装器注册、完成邮箱验证。
3. 在 Word、PDF 阅读器等应用中按 **Ctrl+P**，选择 **算法实验室·惠普打印机**。

## 功能

- 使用 Windows 自带 IPP 驱动，无需安装惠普专用驱动。
- 实验室内网优先直连，公网通过账号授权打印。
- 支持重复、覆盖安装，复用已有打印队列。
- 显示打印机状态、缺纸与墨量，提供公开 [状态 API](https://hp.icthub.top/v1/status)。

服务端采用 **Python + uv + CUPS**，安装器采用 **C# WPF**。CLI 打印、队列管理和 DOCX 上传转换待实现。

## 文档

[安装与运维](docs/09-windows-release.md) · [状态 API](docs/10-status-api.md) · [开发计划](docs/README.md) · [进度与验收](docs/progress.md)
