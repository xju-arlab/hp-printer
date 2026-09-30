using System.Net.Http;
using System.Text.Json;
using System.Windows;
using System.Windows.Media;
using System.Windows.Threading;

namespace ICTHubPrinter.Setup;

public partial class MainWindow
{
    // Keep telemetry independent of the login worker and its credential pipe.
    private readonly HttpClient telemetry = new(new HttpClientHandler { AllowAutoRedirect = false, UseProxy = false })
    {
        Timeout = TimeSpan.FromSeconds(6), MaxResponseContentBufferSize = 128 * 1024,
    };
    private readonly DispatcherTimer telemetryTimer = new() { Interval = TimeSpan.FromSeconds(15) };
    private readonly CancellationTokenSource telemetryCancellation = new();
    private bool refreshingTelemetry;
    private DateTimeOffset? observedAt;
    private string deviceState = "unknown";

    public sealed record SupplyRow(string Name, string Label, double Width, Brush Brush, bool Low = false);

    private void InitializeTelemetry()
    {
        SupplyList.ItemsSource = EmptySupplies();
        telemetryTimer.Tick += async (_, _) => await RefreshTelemetry();
    }

    private void StartTelemetry()
    {
        telemetryTimer.Start();
        _ = RefreshTelemetry();
    }

    private void StopTelemetry()
    {
        telemetryTimer.Stop();
        telemetryCancellation.Cancel();
        telemetry.Dispose();
        telemetryCancellation.Dispose();
    }

    private SupplyRow[] EmptySupplies() =>
    [
        new("黑色墨盒", "—", 0, UiBrush("Muted")),
        new("彩色墨盒", "—", 0, UiBrush("Muted")),
    ];

    private async Task RefreshTelemetry()
    {
        if (refreshingTelemetry || telemetryCancellation.IsCancellationRequested) return;
        refreshingTelemetry = true;
        try
        {
            using var response = await telemetry.GetAsync("https://hp.icthub.top/v1/status", telemetryCancellation.Token);
            response.EnsureSuccessStatusCode();
            using var document = JsonDocument.Parse(await response.Content.ReadAsStringAsync(telemetryCancellation.Token));
            if (telemetryCancellation.IsCancellationRequested) return;
            var printer = document.RootElement;
            var stale = Flag(printer, "stale") || !Flag(printer, "online");
            observedAt = DateTimeOffset.TryParse(Text(printer, "observedAt"), out var time) ? time : null;
            var state = stale ? "unknown" : Text(printer, "state");
            deviceState = state;
            DeviceStatusLabel.Text = state switch { "idle" => "空闲", "processing" => "打印中", "stopped" => "已停止", _ => "暂不可读" };
            PaperStatusLabel.Text = stale ? "—" : Flag(printer, "paperEmpty") ? "缺纸"
                : Flag(printer, "paperLow") ? "纸张不足"
                : printer.TryGetProperty("paperEmpty", out var empty) && empty.ValueKind == JsonValueKind.False ? "未报缺纸" : "—";
            var rows = new List<SupplyRow>();
            if (printer.TryGetProperty("supplies", out var supplies) && supplies.ValueKind == JsonValueKind.Array)
            {
                foreach (var supply in supplies.EnumerateArray().Take(4))
                {
                    int? level = supply.TryGetProperty("levelPercent", out var value) && value.ValueKind == JsonValueKind.Number
                        && value.TryGetInt32(out var number) && number is >= 0 and <= 100 ? number : null;
                    rows.Add(new SupplyRow(Text(supply, "name"), level is null ? "—" : $"{level}%",
                        level.GetValueOrDefault() * 1.83, UiBrush(Flag(supply, "low") ? "Error" : "Muted"), Flag(supply, "low")));
                }
            }
            SupplyList.ItemsSource = rows.Count == 0 ? EmptySupplies() : rows.OrderBy(r => r.Name == "黑色墨盒" ? 0 : 1).ToArray();
            SupplyList.Opacity = stale ? 0.5 : 1;
            UpdateTelemetryColors();
            ShowObservedTime(stale);
        }
        catch (Exception error) when (error is HttpRequestException or TaskCanceledException or JsonException or InvalidOperationException)
        {
            if (telemetryCancellation.IsCancellationRequested) return;
            DeviceStatusLabel.Text = "暂不可读";
            deviceState = "unknown";
            UpdateTelemetryColors();
            PaperStatusLabel.Text = "—";
            SupplyList.Opacity = 0.5;
            ShowObservedTime(true);
        }
        finally { refreshingTelemetry = false; }
    }

    private void ShowObservedTime(bool stale)
    {
        LastUpdated.Text = observedAt is { } time ? $"{(stale ? "上次读数" : "更新于")} {time.ToLocalTime():HH:mm}" : "";
        LastUpdated.ToolTip = observedAt?.ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss");
    }

    private void UpdateTelemetryColors()
    {
        DeviceStatusDot.Fill = UiBrush(deviceState switch { "idle" => "Success", "processing" => "Active", "stopped" => "Error", _ => "Faint" });
        if (SupplyList.ItemsSource is IEnumerable<SupplyRow> rows)
            SupplyList.ItemsSource = rows.Select(row => row with { Brush = UiBrush(row.Low ? "Error" : "Muted") }).ToArray();
    }
}
