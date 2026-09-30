using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace ICTHubPrinter.Setup;

public partial class MainWindow
{
    private static readonly int[] logoSizes = [48, 60, 72, 96, 120, 144, 192];
    private int logoPixelSize;

    private void InitializeTheme()
    {
        Theme.Changed += ApplyWindowTheme;
        SourceInitialized += (_, _) => ApplyWindowTheme();
        DpiChanged += (_, args) => UpdateLogoForDpi(args.NewDpi.DpiScaleX);
        ApplyWindowTheme();
    }

    private Brush UiBrush(string key) => (Brush)FindResource(key);

    private void ApplyWindowTheme()
    {
        // The window uses the original multi-size ICO, avoiding a second resize
        // of a 64 px intermediate bitmap for the small caption icon.
        UpdateTelemetryColors();
        UpdateLogoForDpi();

        var handle = new WindowInteropHelper(this).Handle;
        if (handle == IntPtr.Zero || !OperatingSystem.IsWindowsVersionAtLeast(10, 0, 22000)) return;
        uint caption = WindowColor("Subtle"), text = WindowColor("Ink"), border = WindowColor("Line");
        DwmSetWindowAttribute(handle, 34, ref border, sizeof(uint));
        DwmSetWindowAttribute(handle, 35, ref caption, sizeof(uint));
        DwmSetWindowAttribute(handle, 36, ref text, sizeof(uint));
    }

    private void UpdateLogoForDpi(double? scale = null)
    {
        var pixels = (int)Math.Ceiling(LabLogo.Width * (scale ?? VisualTreeHelper.GetDpi(this).DpiScaleX));
        var size = logoSizes.FirstOrDefault(value => value >= pixels, logoSizes[^1]);
        if (size == logoPixelSize) return;
        var image = new BitmapImage(new Uri($"pack://application:,,,/Assets/Logo/lab-logo-{size}.png"));
        image.Freeze();
        LabLogo.Source = image;
        logoPixelSize = size;
    }

    private uint WindowColor(string name)
    {
        var color = ((SolidColorBrush)UiBrush(name)).Color;
        return (uint)(color.R | color.G << 8 | color.B << 16);
    }

    [DllImport("dwmapi.dll")]
    private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref uint value, int size);
}
