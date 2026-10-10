import AppKit
import SwiftUI

@main
struct ICTHubPrinterMacApp: App {
    var body: some Scene {
        WindowGroup {
            PrinterView()
                .frame(minWidth: 430, minHeight: 270)
        }
        .windowResizability(.contentSize)
    }
}

struct PrinterView: View {
    @State private var message = "正在读取打印机状态…"
    @State private var busy = false
    @State private var isInstalled = false
    @State private var isLoggedIn = false

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 12) {
                Image(systemName: "printer.fill")
                    .font(.system(size: 28))
                    .foregroundStyle(.tint)
                    .frame(width: 42)
                VStack(alignment: .leading, spacing: 4) {
                    Text("算法实验室·惠普打印机")
                        .font(.title2.weight(.semibold))
                    Text("ICTHub Printer")
                        .foregroundStyle(.secondary)
                }
            }

            HStack(alignment: .top, spacing: 10) {
                Image(systemName: isInstalled ? "checkmark.circle.fill" : "info.circle")
                    .foregroundStyle(isInstalled ? .green : .secondary)
                    .padding(.top, 2)
                Text(message)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            HStack {
                Button(isInstalled ? "修复打印机" : "添加打印机") {
                    perform("install", progress: "正在连接打印服务；如浏览器打开，请完成账号登录…")
                }
                .buttonStyle(.borderedProminent)
                .disabled(busy)

                Button("登录账号") {
                    perform("login", progress: "正在打开 ICTHub 登录…")
                }
                .buttonStyle(.bordered)
                .disabled(busy)

                Button("移除") {
                    perform("uninstall", progress: "正在移除打印机…")
                }
                .buttonStyle(.bordered)
                .disabled(busy || !isInstalled)

                Spacer()

                Button {
                    NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.Print-Scan-Settings.extension")!)
                } label: {
                    Image(systemName: "gearshape")
                }
                .buttonStyle(.borderless)
                .help("打开打印机设置")
                .disabled(busy)
            }
        }
        .padding(24)
        .onAppear { perform("status", progress: "正在读取打印机状态…") }
    }

    private func perform(_ command: String, progress: String) {
        busy = true
        message = progress
        DispatchQueue.global(qos: .userInitiated).async {
            let result = Self.runBackend(command)
            DispatchQueue.main.async {
                busy = false
                if let result, result["ok"] as? Bool == true {
                    let route = result["route"] as? String
                    if command == "status" {
                        isInstalled = result["installed"] as? Bool == true
                        isLoggedIn = result["loggedIn"] as? Bool == true
                        if !isInstalled {
                            message = "尚未添加打印机。"
                        } else if route == "lan" {
                            message = isLoggedIn
                                ? "已添加，当前使用实验室内网；账号授权可用于外网打印。"
                                : "已添加，当前使用实验室内网；离开内网前请登录账号。"
                        } else if result["loginRequired"] as? Bool == true {
                            message = "打印授权已失效，请登录账号后继续使用。"
                        } else {
                            message = "已添加，当前通过账号授权连接。"
                        }
                    } else if command == "install" {
                        isInstalled = true
                        message = route == "lan"
                            ? "添加完成，已连接实验室内网；此队列也支持外网授权打印。"
                            : "添加完成，打印机已通过账号授权连接。"
                        isLoggedIn = route == "remote" || isLoggedIn
                    } else if command == "login" {
                        isLoggedIn = true
                        message = "ICTHub 账号已登录，可用于外网打印。"
                    } else {
                        isInstalled = false
                        isLoggedIn = false
                        message = "打印机和本机授权已移除。"
                    }
                } else {
                    message = result?["message"] as? String ?? "操作未完成，请检查网络后重试。"
                }
            }
        }
    }

    private static func runBackend(_ command: String) -> [String: Any]? {
        let executable = Bundle.main.bundleURL
            .appendingPathComponent("Contents/MacOS/ICTHubPrinterBackend").path
        let process = Process()
        let output = Pipe()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = [command]
        process.standardOutput = output
        process.standardError = FileHandle.nullDevice
        do {
            try process.run()
            process.waitUntilExit()
            let data = output.fileHandleForReading.readDataToEndOfFile()
            return try JSONSerialization.jsonObject(with: data) as? [String: Any]
        } catch {
            return nil
        }
    }
}
