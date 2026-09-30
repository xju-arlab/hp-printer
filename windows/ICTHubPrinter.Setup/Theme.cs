using System.ComponentModel;
using System.Windows;
using System.Windows.Media;

namespace ICTHubPrinter.Setup;

internal static class Theme
{
    public static event Action? Changed;
    public static void Start()
    {
        Apply();
        SystemParameters.StaticPropertyChanged += SystemParameterChanged;
    }

    public static void Stop()
    {
        SystemParameters.StaticPropertyChanged -= SystemParameterChanged;
    }

    private static void SystemParameterChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(SystemParameters.HighContrast)) Schedule();
    }

    private static void Schedule()
    {
        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher is not null && !dispatcher.HasShutdownStarted)
            dispatcher.BeginInvoke(new Action(Apply));
    }

    private static void Apply()
    {
        // The installer opens in light mode regardless of the Windows app theme.
        // Explicit system high-contrast settings still take precedence below.
        var palette = new Dictionary<string, string>
        {
            ["Canvas"] = "#FFFFFF", ["Ink"] = "#37352F", ["Muted"] = "#787774",
            ["Faint"] = "#9B9A97", ["Subtle"] = "#F7F6F3", ["Line"] = "#EDECE9",
            ["LineStrong"] = "#DCDAD4", ["Hover"] = "#F1F1EF", ["Track"] = "#E5E3DE",
            ["PrimaryBg"] = "#37352F", ["PrimaryFg"] = "#FFFFFF", ["Error"] = "#B44040",
            ["Success"] = "#0F7B6C", ["Active"] = "#2383E2",
        };
        foreach (var (name, hex) in palette)
        {
            var color = (Color)ColorConverter.ConvertFromString(hex);
            if (SystemParameters.HighContrast)
                color = name switch
                {
                    "Canvas" or "Subtle" or "Hover" or "PrimaryFg" => SystemColors.WindowColor,
                    _ => SystemColors.WindowTextColor,
                };
            var brush = new SolidColorBrush(color);
            brush.Freeze();
            Application.Current.Resources[name] = brush;
        }
        Changed?.Invoke();
    }
}
