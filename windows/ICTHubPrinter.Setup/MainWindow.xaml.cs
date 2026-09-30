using System.ComponentModel;
using System.IO;
using System.Text.Json;
using System.Windows;

namespace ICTHubPrinter.Setup;

public partial class MainWindow : Window
{
    private Backend backend = new();
    private string stage = "welcome";
    private bool busy;
    private bool changingInstallation;
    private readonly bool loginOnly;

    public MainWindow()
    {
        InitializeComponent();
        var command = Environment.GetCommandLineArgs().Skip(1).FirstOrDefault();
        loginOnly = command == "login";
        Welcome();
        Loaded += async (_, _) =>
        {
            if (command == "status") await ShowStatus();
            else if (command == "uninstall") ShowUninstall();
            else if (loginOnly) await StartLogin();
        };
    }

    private void Page(string next, string heading, string description, string primary)
    {
        stage = next;
        Heading.Text = heading;
        Description.Text = description;
        Primary.Content = primary;
        Secondary.Content = "返回";
        Secondary.Visibility = Visibility.Visible;
        UsernamePanel.Visibility = PasswordPanel.Visibility = CodePanel.Visibility = Visibility.Collapsed;
        SavedLogin.Visibility = DetailPanel.Visibility = Visibility.Collapsed;
        ErrorText.Text = ProgressText.Text = "";
        Password.Clear();
        Code.Clear();
        StepText.Text = next switch
        {
            "identity" or "password" or "code" or "consent" => "01 / 登录账号",
            "ready" => "02 / 安装打印机",
            "done" => "已完成",
            "status" => "设备与连接",
            "uninstall" => "管理打印机",
            _ => "开始使用",
        };
    }

    private void Detail(string text)
    {
        Details.Text = text;
        DetailPanel.Visibility = Visibility.Visible;
    }

    private void Welcome()
    {
        Page("welcome", "安装实验室打印机", "登录算法实验室账号后，即可在 Word、PDF 阅读器等应用中使用这台打印机。", "登录并继续");
        Detail("算法实验室·惠普打印机\n\n安装完成后，按 Ctrl+P 选择打印机即可。\n无需安装惠普专用驱动。");
        Secondary.Content = "关闭";
        var credentials = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ICTHubPrinter", "credentials.dpapi");
        SavedLogin.Visibility = File.Exists(credentials) ? Visibility.Visible : Visibility.Collapsed;
    }

    private async Task Execute(Func<Task> action, bool installation = false)
    {
        if (busy) return;
        busy = true;
        changingInstallation = installation;
        Primary.IsEnabled = Secondary.IsEnabled = SavedLogin.IsEnabled = StatusButton.IsEnabled = UninstallButton.IsEnabled = false;
        Username.IsEnabled = Password.IsEnabled = Code.IsEnabled = false;
        ErrorText.Text = "";
        Progress.Visibility = Visibility.Visible;
        try { await action(); }
        catch (InvalidOperationException ex) { ErrorText.Text = ex.Message; }
        catch (Exception) { ErrorText.Text = "安装组件暂时不可用，请关闭其他安装窗口后重试。"; }
        finally
        {
            busy = changingInstallation = false;
            Primary.IsEnabled = Secondary.IsEnabled = SavedLogin.IsEnabled = StatusButton.IsEnabled = UninstallButton.IsEnabled = true;
            Username.IsEnabled = Password.IsEnabled = Code.IsEnabled = true;
            Progress.Visibility = Visibility.Collapsed;
        }
    }

    private Task<JsonElement> Send(string command, object? values = null) =>
        backend.SendAsync(command, values, message => ProgressText.Text = message);

    private Task StartLogin() => Execute(async () =>
    {
        ProgressText.Text = "正在连接算法实验室账号服务…";
        ShowChallenge(await Send("start-login"));
    });

    private void ShowChallenge(JsonElement result)
    {
        var next = Text(result, "stage");
        switch (next)
        {
            case "identity":
                Page(next, "登录 算法实验室", "使用已注册并验证邮箱的账号。验证会在此窗口内完成。", "登录");
                UsernamePanel.Visibility = Visibility.Visible;
                if (Flag(result, "password")) PasswordPanel.Visibility = Visibility.Visible;
                Username.Focus();
                break;
            case "password":
                Page(next, "输入账号密码", "请继续完成算法实验室账号验证。", "继续");
                PasswordPanel.Visibility = Visibility.Visible;
                Password.Focus();
                break;
            case "code":
                Page(next, "验证你的身份", "请填写身份验证器中的动态验证码，或一个未使用的恢复码。", "验证");
                CodePanel.Visibility = Visibility.Visible;
                Code.Focus();
                break;
            case "consent":
                Page(next, "允许打印机连接", "授权后，这台电脑可使用你的账号连接实验室公网打印服务。", "允许并继续");
                var permissions = result.GetProperty("permissions").EnumerateArray().Select(p => p.GetString());
                Detail("申请的账号权限\n\n" + string.Join("\n", permissions));
                break;
            case "authenticated":
                if (loginOnly)
                {
                    Page("done", "登录成功", "账号授权已保存，打印后台会在下一次请求时使用新的授权。", "完成");
                    Detail("当前账号：" + Text(result, "username"));
                    Secondary.Visibility = Visibility.Collapsed;
                }
                else
                {
                    Page("ready", "准备安装", "安装时若出现 Windows 权限提示，请选择“是”。", "安装打印机");
                    Detail("当前账号：" + Text(result, "username") + "\n\n算法实验室·惠普打印机\n内网优先 · 支持公网连接\n已安装的用户将更新打印后台。");
                }
                break;
            default: throw new InvalidOperationException("登录流程已改变，请返回后重新登录。");
        }
        var message = Text(result, "message");
        if (!string.IsNullOrEmpty(message)) ErrorText.Text = message;
    }

    private async void Primary_Click(object sender, RoutedEventArgs e)
    {
        if (busy) return;
        switch (stage)
        {
            case "welcome": await StartLogin(); break;
            case "identity":
            case "password":
            case "code":
            case "consent":
                if (stage == "identity" && string.IsNullOrWhiteSpace(Username.Text)) { ErrorText.Text = "请输入账号或邮箱。"; return; }
                if (PasswordPanel.IsVisible && Password.Password.Length == 0) { ErrorText.Text = "请输入密码。"; return; }
                if (stage == "code" && Code.Password.Length == 0) { ErrorText.Text = "请输入验证码或恢复码。"; return; }
                await Execute(async () =>
                {
                    var submission = Send("respond-login", new { username = Username.Text, password = Password.Password, code = Code.Password, accept = stage == "consent" });
                    Password.Clear(); Code.Clear();
                    ShowChallenge(await submission);
                });
                break;
            case "ready":
                await Execute(async () =>
                {
                    ProgressText.Text = "正在准备安装…";
                    await Send("install", new { gui_path = Environment.ProcessPath });
                    Page("done", "打印机已就绪", "打开 Word 或 PDF 阅读器，按 Ctrl+P 选择下面的打印机。", "完成");
                    Detail("算法实验室·惠普打印机\n\n打印后台会随 Windows 登录自动启动。\n可在开始菜单中查看状态或重新登录。");
                    Secondary.Visibility = Visibility.Collapsed;
                }, installation: true);
                break;
            case "status": await ShowStatus(); break;
            case "uninstall":
                await Execute(async () =>
                {
                    ProgressText.Text = "正在移除打印机和本机授权…";
                    await Send("uninstall");
                    Page("done", "卸载完成", "打印机、开机启动和本机登录授权已移除。诊断日志保留在安装目录。", "关闭");
                    Secondary.Visibility = Visibility.Collapsed;
                }, installation: true);
                break;
            case "done": Close(); break;
        }
    }

    private void Secondary_Click(object sender, RoutedEventArgs e)
    {
        if (stage == "welcome") { Close(); return; }
        backend.Dispose(); backend = new Backend();
        Welcome();
    }

    private async void SavedLogin_Click(object sender, RoutedEventArgs e) => await Execute(async () => ShowChallenge(await Send("reuse-login")));
    private async void Status_Click(object sender, RoutedEventArgs e) => await ShowStatus();
    private void Uninstall_Click(object sender, RoutedEventArgs e) => ShowUninstall();

    private void ShowUninstall()
    {
        Page("uninstall", "卸载打印机", "将从当前 Windows 用户中移除实验室打印机、登录授权和开机启动。", "确认卸载");
        Detail("算法实验室·惠普打印机\n\n其他打印机不受影响。");
    }

    private Task ShowStatus() => Execute(async () =>
    {
        Page("status", "打印机状态", "查看本机后台与实验室打印设备的当前状态。", "刷新状态");
        var result = await Send("status");
        var route = Text(result, "route") switch { "lan" => "实验室内网", "remote" => "公网", _ => "尚未发送打印任务" };
        var lines = new List<string>
        {
            "系统打印机：" + (Flag(result, "installed") ? "已安装" : "未安装"),
            "本机打印后台：" + (Flag(result, "running") ? "运行中" : "未运行"),
            "最近打印通道：" + route,
        };
        if (Flag(result, "login_required")) lines.Add("账号：需要重新登录");
        if (result.TryGetProperty("printer", out var printer))
        {
            lines.Add("");
            lines.Add("设备：" + Text(printer, "stateLabel"));
            lines.Add("纸张：" + Text(printer, "paperLabel"));
            if (printer.TryGetProperty("supplies", out var supplies))
            {
                foreach (var supply in supplies.EnumerateArray())
                    lines.Add(Text(supply, "name") + "：" + Text(supply, "levelLabel"));
                if (supplies.GetArrayLength() == 0) lines.Add("墨量：暂不可读");
            }
            if (Flag(printer, "stale")) lines.Add("设备信息已过期，正在等待新的读数。");
        }
        else lines.Add("\n暂时无法读取实验室设备信息。");
        Detail(string.Join("\n", lines));
    });

    private static string Text(JsonElement value, string key) => value.TryGetProperty(key, out var item) && item.ValueKind == JsonValueKind.String ? item.GetString() ?? "" : "";
    private static bool Flag(JsonElement value, string key) => value.TryGetProperty(key, out var item) && item.ValueKind == JsonValueKind.True;

    protected override void OnClosing(CancelEventArgs e)
    {
        if (changingInstallation)
        {
            e.Cancel = true;
            ProgressText.Text = "正在更新打印机，请等待操作结束后关闭。";
        }
        else backend.Dispose();
        base.OnClosing(e);
    }
}
