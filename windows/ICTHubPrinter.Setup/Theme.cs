using Microsoft.Win32;
using System.ComponentModel;
using System.Windows;
using System.Windows.Media;

namespace ICTHubPrinter.Setup;

internal static class Theme
{
    public static event Action? Changed;
    public static bool Dark { get; private set; }

    public static void Start()
    {
        Apply();
        SystemEvents.UserPreferenceChanged += PreferenceChanged;
        SystemParameters.StaticPropertyChanged += SystemParameterChanged;
    }

    public static void Stop()
    {
        SystemEvents.UserPreferenceChanged -= PreferenceChanged;
        SystemParameters.StaticPropertyChanged -= SystemParameterChanged;
    }

    private static void PreferenceChanged(object sender, UserPreferenceChangedEventArgs e) => Schedule();
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
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize");
            Dark = key?.GetValue("AppsUseLightTheme") is int value && value == 0;
        }
        catch (Exception error) when (error is System.Security.SecurityException or UnauthorizedAccessException)
        {
            Dark = false;
        }

        var palette = Dark ? new Dictionary<string, string>
        {
            ["Canvas"] = "#191919", ["Ink"] = "#E6E3DF", ["Muted"] = "#AAA8A3",
            ["Faint"] = "#8D8B86", ["Subtle"] = "#202020", ["Line"] = "#323230",
            ["LineStrong"] = "#494844", ["Hover"] = "#2C2C2A", ["Track"] = "#3C3B38",
            ["PrimaryBg"] = "#E6E3DF", ["PrimaryFg"] = "#191919", ["Error"] = "#EE9288",
            ["Success"] = "#6CBAA9", ["Active"] = "#78B7ED",
        } : new Dictionary<string, string>
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
