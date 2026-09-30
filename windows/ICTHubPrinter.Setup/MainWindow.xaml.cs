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
        InitializeTelemetry();
        InitializeTheme();
        var command = Environment.GetCommandLineArgs().Skip(1).FirstOrDefault();
        loginOnly = command == "login";
        Welcome();
        Loaded += async (_, _) =>
        {
            StartTelemetry();
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
        Description.Visibility = string.IsNullOrEmpty(description) ? Visibility.Collapsed : Visibility.Visible;
        Primary.Content = primary;
        Secondary.Content = "返回";
        Secondary.Visibility = Visibility.Visible;
        UsernamePanel.Visibility = PasswordPanel.Visibility = CodePanel.Visibility = Visibility.Collapsed;
        EmailPanel.Visibility = PasswordRepeatPanel.Visibility = RegistrationPasswordHint.Visibility = Visibility.Collapsed;
        RegisterButton.Visibility = ResendButton.Visibility = Visibility.Collapsed;
        UsernameLabel.Content = "账号或邮箱";
        Username.MaxLength = 254;
        SavedLogin.Visibility = DetailPanel.Visibility = Visibility.Collapsed;
        ErrorText.Text = ProgressText.Text = "";
    }

    private void ClearLoginInputs()
    {
        Password.Clear();
        Code.Clear();
        PasswordRepeat.Clear();
    }

    private void Detail(string text)
    {
        Details.Text = text;
        DetailPanel.Visibility = Visibility.Visible;
    }

    private void Welcome()
    {
        ClearLoginInputs();
        Page("welcome", "安装打印机", "", "登录");
        Detail("算法实验室·惠普打印机");
        Secondary.Content = "关闭";
        var credentials = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ICTHubPrinter", "credentials.dpapi");
        SavedLogin.Visibility = File.Exists(credentials) ? Visibility.Visible : Visibility.Collapsed;
        RegisterButton.Visibility = Visibility.Visible;
    }

    private async Task Execute(Func<Task> action, bool installation = false)
    {
        if (busy) return;
        busy = true;
        changingInstallation = installation;
        Primary.IsEnabled = Secondary.IsEnabled = SavedLogin.IsEnabled = StatusButton.IsEnabled = UninstallButton.IsEnabled = false;
        Username.IsEnabled = Password.IsEnabled = Code.IsEnabled = false;
        Email.IsEnabled = PasswordRepeat.IsEnabled = RegisterButton.IsEnabled = ResendButton.IsEnabled = false;
        ErrorText.Text = "";
        Progress.Visibility = Visibility.Visible;
        try { await action(); }
        catch (InvalidOperationException ex) { ErrorText.Text = ex.Message; }
        catch (Exception) { ErrorText.Text = "暂时无法连接安装组件，请重试。"; }
        finally
        {
            busy = changingInstallation = false;
            Primary.IsEnabled = Secondary.IsEnabled = SavedLogin.IsEnabled = StatusButton.IsEnabled = UninstallButton.IsEnabled = true;
            Username.IsEnabled = Password.IsEnabled = Code.IsEnabled = true;
            Email.IsEnabled = PasswordRepeat.IsEnabled = RegisterButton.IsEnabled = ResendButton.IsEnabled = true;
            Progress.Visibility = Visibility.Collapsed;
            ProgressText.Text = "";
            FocusLoginInput();
        }
    }

    private void FocusLoginInput()
    {
        if (stage == "registration")
        {
            if (string.IsNullOrWhiteSpace(Username.Text)) Username.Focus();
            else if (string.IsNullOrWhiteSpace(Email.Text)) Email.Focus();
            else if (Password.Password.Length == 0) Password.Focus();
            else PasswordRepeat.Focus();
        }
        else if (stage == "code") Code.Focus();
        else if (stage == "password" || (stage == "identity" && PasswordPanel.IsVisible && !string.IsNullOrWhiteSpace(Username.Text))) Password.Focus();
        else if (stage == "identity") Username.Focus();
    }

    private Task<JsonElement> Send(string command, object? values = null) =>
        backend.SendAsync(command, values, message => ProgressText.Text = message);

    private Task StartLogin() => Execute(async () =>
    {
        ProgressText.Text = "连接中…";
        ShowChallenge(await Send("start-login"));
    });

    private void ShowChallenge(JsonElement result)
    {
        var next = Text(result, "stage");
        switch (next)
        {
            case "identity":
                Page(next, "登录", "", "登录");
                UsernamePanel.Visibility = Visibility.Visible;
                if (Flag(result, "password")) PasswordPanel.Visibility = Visibility.Visible;
                RegisterButton.Visibility = Visibility.Visible;
                break;
            case "registration":
                Page(next, "注册账号", "", "注册");
                UsernameLabel.Content = "用户名";
                Username.MaxLength = 32;
                UsernamePanel.Visibility = EmailPanel.Visibility = PasswordPanel.Visibility = PasswordRepeatPanel.Visibility = Visibility.Visible;
                RegistrationPasswordHint.Visibility = Visibility.Visible;
                break;
            case "registration-email":
                ClearLoginInputs();
                Page(next, "验证邮箱", "点击邮件中的验证链接，完成后返回登录。", "已验证，登录");
                Detail(Email.Text.Trim());
                ResendButton.Visibility = Visibility.Visible;
                break;
            case "password":
                Page(next, "输入密码", "", "继续");
                PasswordPanel.Visibility = Visibility.Visible;
                break;
            case "code":
                Page(next, "动态验证码(Authenticator)", "", "验证");
                CodePanel.Visibility = Visibility.Visible;
                break;
            case "consent":
                Page(next, "授权打印", "允许此电脑使用你的账号打印。", "允许");
                var permissions = result.GetProperty("permissions").EnumerateArray().Select(p => p.GetString());
                Detail(string.Join("\n", permissions));
                break;
            case "authenticated":
                ClearLoginInputs();
                if (loginOnly)
                {
                    Page("done", "已登录", "", "完成");
                    Detail("当前账号：" + Text(result, "username"));
                    Secondary.Visibility = Visibility.Collapsed;
                }
                else
                {
                    Page("ready", "安装打印机", "", "安装");
                    Detail("算法实验室·惠普打印机\n账号：" + Text(result, "username"));
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
            case "registration":
                if (string.IsNullOrWhiteSpace(Username.Text)) { ErrorText.Text = "请输入用户名。"; return; }
                if (string.IsNullOrWhiteSpace(Email.Text)) { ErrorText.Text = "请输入邮箱。"; return; }
                if (Password.Password.Length == 0) { ErrorText.Text = "请输入密码。"; return; }
                if (PasswordRepeat.Password != Password.Password) { ErrorText.Text = "两次密码不一致。"; return; }
                await Execute(async () => ShowChallenge(await Send("submit-registration", new
                {
                    username = Username.Text, email = Email.Text,
                    password = Password.Password, password_repeat = PasswordRepeat.Password,
                })));
                break;
            case "registration-email": await StartLogin(); break;
            case "identity":
            case "password":
            case "code":
            case "consent":
                if (stage == "identity" && string.IsNullOrWhiteSpace(Username.Text)) { ErrorText.Text = "请输入账号或邮箱。"; return; }
                if (PasswordPanel.IsVisible && Password.Password.Length == 0) { ErrorText.Text = "请输入密码。"; return; }
                if (stage == "code" && Code.Password.Length == 0) { ErrorText.Text = "请输入动态验证码。"; return; }
                await Execute(async () =>
                {
                    // Keep typed values through pending requests, validation
                    // errors and network failures. Send only this stage's fields.
                    object values = stage switch
                    {
                        "identity" => new { username = Username.Text, password = PasswordPanel.IsVisible ? Password.Password : "" },
                        "password" => new { password = Password.Password },
                        "code" => new { code = Code.Password },
                        "consent" => new { accept = true },
                        _ => throw new InvalidOperationException("请重新登录。"),
                    };
                    ShowChallenge(await Send("respond-login", values));
                });
                break;
            case "ready":
                await Execute(async () =>
                {
                    ProgressText.Text = "安装中…";
                    await Send("install", new { gui_path = Environment.ProcessPath });
                    Page("done", "已安装", "按 Ctrl+P 选择打印机。", "完成");
                    Detail("算法实验室·惠普打印机");
                    Secondary.Visibility = Visibility.Collapsed;
                }, installation: true);
                break;
            case "status": await ShowStatus(); break;
            case "uninstall":
                await Execute(async () =>
                {
                    ProgressText.Text = "卸载中…";
                    await Send("uninstall");
                    Page("done", "已卸载", "", "关闭");
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
    private async void Register_Click(object sender, RoutedEventArgs e) => await Execute(async () =>
    {
        ClearLoginInputs();
        Username.Clear();
        Email.Clear();
        ShowChallenge(await Send("start-registration"));
    });
    private async void Resend_Click(object sender, RoutedEventArgs e) =>
        await Execute(async () => ShowChallenge(await Send("resend-registration")));
    private async void Status_Click(object sender, RoutedEventArgs e) => await ShowStatus();
    private void Uninstall_Click(object sender, RoutedEventArgs e) => ShowUninstall();

    private void ShowUninstall()
    {
        ClearLoginInputs();
        Page("uninstall", "卸载打印机", "移除本机打印机、登录信息和开机启动。", "卸载");
        Detail("算法实验室·惠普打印机");
    }

    private Task ShowStatus() => Execute(async () =>
    {
        ClearLoginInputs();
        Page("status", "本机状态", "", "刷新");
        var result = await Send("status");
        var route = Text(result, "route") switch { "lan" => "实验室内网", "remote" => "公网", _ => "—" };
        var lines = new List<string>
        {
            "打印机：" + (Flag(result, "installed") ? "已安装" : "未安装"),
            "打印服务：" + (Flag(result, "running") ? "运行中" : "未运行"),
            "最近通道：" + route,
        };
        if (Flag(result, "login_required")) lines.Add("账号：需要重新登录");
        Detail(string.Join("\n", lines));
    });

    private static string Text(JsonElement value, string key) => value.TryGetProperty(key, out var item) && item.ValueKind == JsonValueKind.String ? item.GetString() ?? "" : "";
    private static bool Flag(JsonElement value, string key) => value.TryGetProperty(key, out var item) && item.ValueKind == JsonValueKind.True;

    protected override void OnClosing(CancelEventArgs e)
    {
        if (changingInstallation)
        {
            e.Cancel = true;
            ProgressText.Text = "操作中，请稍候。";
        }
        else backend.Dispose();
        base.OnClosing(e);
    }

    protected override void OnClosed(EventArgs e)
    {
        ClearLoginInputs();
        StopTelemetry();
        Theme.Changed -= ApplyWindowTheme;
        base.OnClosed(e);
    }
}
