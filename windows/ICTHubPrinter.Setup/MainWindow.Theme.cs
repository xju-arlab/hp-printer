using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace ICTHubPrinter.Setup;

public partial class MainWindow
{
    private readonly BitmapImage printerMask = new(new Uri("pack://application:,,,/Assets/printer.png"));

    private void InitializeTheme()
    {
        Theme.Changed += ApplyWindowTheme;
        SourceInitialized += (_, _) => ApplyWindowTheme();
        ApplyWindowTheme();
    }

    private Brush UiBrush(string key) => (Brush)FindResource(key);

    private void ApplyWindowTheme()
    {
        // Tint the provided transparent shape at render time; preserve its pixels.
        var visual = new DrawingVisual();
        using (var drawing = visual.RenderOpen())
        {
            drawing.PushOpacityMask(new ImageBrush(printerMask) { Stretch = Stretch.Uniform });
            drawing.DrawRectangle(UiBrush("Ink"), null, new Rect(0, 0, 64, 64));
            drawing.Pop();
        }
        var icon = new RenderTargetBitmap(64, 64, 96, 96, PixelFormats.Pbgra32);
        icon.Render(visual);
        icon.Freeze();
        Icon = icon;
        UpdateTelemetryColors();

        var handle = new WindowInteropHelper(this).Handle;
        if (handle == IntPtr.Zero || !OperatingSystem.IsWindowsVersionAtLeast(10, 0, 22000)) return;
        uint caption = WindowColor("Subtle"), text = WindowColor("Ink"), border = WindowColor("Line");
        DwmSetWindowAttribute(handle, 34, ref border, sizeof(uint));
        DwmSetWindowAttribute(handle, 35, ref caption, sizeof(uint));
        DwmSetWindowAttribute(handle, 36, ref text, sizeof(uint));
    }

    private uint WindowColor(string name)
    {
        var color = ((SolidColorBrush)UiBrush(name)).Color;
        return (uint)(color.R | color.G << 8 | color.B << 16);
    }

    [DllImport("dwmapi.dll")]
    private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref uint value, int size);
}
