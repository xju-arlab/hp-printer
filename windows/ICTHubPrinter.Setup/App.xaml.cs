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
            MessageBox.Show("安装器已打开。", "算法与科研实验室");
            Shutdown();
            return;
        }
        Theme.Start();
        base.OnStartup(e);
    }

    protected override void OnExit(ExitEventArgs e)
    {
        Theme.Stop();
        instance?.Dispose();
        base.OnExit(e);
    }
}
