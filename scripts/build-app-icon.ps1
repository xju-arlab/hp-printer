$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$assets = Join-Path (Split-Path $PSScriptRoot -Parent) 'windows/ICTHubPrinter.Setup/Assets'
$source = [Drawing.Bitmap]::new((Join-Path $assets 'printer.png'))
$frames = [Collections.Generic.List[byte[]]]::new()
$sizes = @(16,24,32,48,64,128,256)
try {
    foreach ($size in $sizes) {
        $bitmap = [Drawing.Bitmap]::new($size,$size)
        $graphics = [Drawing.Graphics]::FromImage($bitmap)
        $stream = [IO.MemoryStream]::new()
        $path = [Drawing.Drawing2D.GraphicsPath]::new()
        $background = [Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(247,246,243))
        try {
            $graphics.Clear([Drawing.Color]::Transparent)
            $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
            $graphics.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            # A neutral tile keeps the static Explorer icon legible on either background.
            # The running window tints the original alpha mask for the current theme.
            $inset = [single]($size * 0.025)
            $diameter = [single]($size * 0.3)
            $edge = [single]($size - $inset - $diameter)
            $path.AddArc($inset,$inset,$diameter,$diameter,180,90)
            $path.AddArc($edge,$inset,$diameter,$diameter,270,90)
            $path.AddArc($edge,$edge,$diameter,$diameter,0,90)
            $path.AddArc($inset,$edge,$diameter,$diameter,90,90)
            $path.CloseFigure()
            $graphics.FillPath($background,$path)
            $graphics.DrawImage($source,[Drawing.Rectangle]::new(0,0,$size,$size))
            $bitmap.Save($stream,[Drawing.Imaging.ImageFormat]::Png)
            $frames.Add($stream.ToArray())
        } finally {
            $background.Dispose(); $path.Dispose(); $stream.Dispose(); $graphics.Dispose(); $bitmap.Dispose()
        }
    }
    $writer = [IO.BinaryWriter]::new([IO.File]::Create((Join-Path $assets 'printer.ico')))
    try {
        $writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]$sizes.Count)
        $offset = 6 + 16 * $sizes.Count
        for ($index=0; $index -lt $sizes.Count; $index++) {
            $dimension = if ($sizes[$index] -eq 256) {0} else {$sizes[$index]}
            $writer.Write([byte]$dimension); $writer.Write([byte]$dimension)
            $writer.Write([byte]0); $writer.Write([byte]0)
            $writer.Write([uint16]1); $writer.Write([uint16]32)
            $writer.Write([uint32]$frames[$index].Length); $writer.Write([uint32]$offset)
            $offset += $frames[$index].Length
        }
        foreach ($frame in $frames) { $writer.Write($frame) }
    } finally { $writer.Dispose() }
} finally { $source.Dispose() }
