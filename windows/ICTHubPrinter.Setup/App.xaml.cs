using System.Windows;
using System.Threading;

namespace ICTHubPrinter.Setup;

public partial class App : Application
{
    private Mutex? instance;

    protected override void OnStartup(StartupEventArgs e)
    {
        instance = new Mutex(true, "Local\\AlgorithmLabPrinterSetup", out var first);
        if (!first)
        {
            MessageBox.Show("打印机安装器已打开，请先关闭其他安装窗口。", "算法实验室");
            Shutdown();
            return;
        }
        base.OnStartup(e);
    }

    protected override void OnExit(ExitEventArgs e)
    {
        instance?.Dispose();
        base.OnExit(e);
    }
}
