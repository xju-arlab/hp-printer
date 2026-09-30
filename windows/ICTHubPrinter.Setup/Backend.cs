using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace ICTHubPrinter.Setup;

internal sealed class Backend : IDisposable
{
    private Process? process;

    private async Task StartAsync()
    {
        if (process is { HasExited: false }) return;
        process?.Dispose();
        using var payload = Assembly.GetExecutingAssembly().GetManifestResourceStream("PrinterBackend.exe")
            ?? throw new IOException("安装包不完整，请重新下载。");
        var digest = Convert.ToHexString(await SHA256.HashDataAsync(payload)).ToLowerInvariant();
        var directory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "ICTHubPrinter", "EngineCache", digest);
        Directory.CreateDirectory(directory);
        var executable = Path.Combine(directory, "ICTHubPrinter.exe");
        var valid = false;
        if (File.Exists(executable))
        {
            using var saved = File.OpenRead(executable);
            valid = Convert.ToHexString(await SHA256.HashDataAsync(saved)).ToLowerInvariant() == digest;
        }
        if (!valid)
        {
            payload.Position = 0;
            var temporary = executable + "." + Guid.NewGuid().ToString("N") + ".tmp";
            try
            {
                using (var file = File.Create(temporary)) await payload.CopyToAsync(file);
                File.Move(temporary, executable, true);
            }
            finally { if (File.Exists(temporary)) File.Delete(temporary); }
        }
        var info = new ProcessStartInfo(executable)
        {
            UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardInputEncoding = new UTF8Encoding(false), StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8, WorkingDirectory = directory,
        };
        info.ArgumentList.Add("gui-backend");
        info.ArgumentList.Add("--no-pause");
        process = Process.Start(info) ?? throw new IOException("无法启动安装组件。");
        // Drain without persisting logs that could contain authentication details.
        process.ErrorDataReceived += (_, _) => { };
        process.BeginErrorReadLine();
    }

    public async Task<JsonElement> SendAsync(string command, object? values, Action<string> progress)
    {
        await StartAsync();
        // Passwords only cross these private redirected pipes, never command arguments.
        await process!.StandardInput.WriteLineAsync(JsonSerializer.Serialize(new { command, values }));
        await process.StandardInput.FlushAsync();
        while (await process.StandardOutput.ReadLineAsync() is { } line)
        {
            using var document = JsonDocument.Parse(line);
            var root = document.RootElement;
            if (root.GetProperty("event").GetString() == "progress")
            {
                progress(root.GetProperty("message").GetString() ?? "");
                continue;
            }
            if (!root.GetProperty("ok").GetBoolean())
                throw new InvalidOperationException(root.GetProperty("message").GetString());
            return root.GetProperty("result").Clone();
        }
        throw new IOException("安装组件已退出，请重新打开安装程序。");
    }

    public void Dispose()
    {
        if (process is null) return;
        // EOF discards the session without killing the installed print agent.
        try { process.StandardInput.Close(); }
        catch (InvalidOperationException) { }
        catch (IOException) { }
        process.Dispose();
        process = null;
    }
}
