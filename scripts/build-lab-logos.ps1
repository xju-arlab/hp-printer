$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$assets = Join-Path (Split-Path $PSScriptRoot -Parent) 'windows/ICTHubPrinter.Setup/Assets'
$output = Join-Path $assets 'Logo'
New-Item -ItemType Directory -Force -Path $output | Out-Null
$source = [Drawing.Bitmap]::new((Join-Path $assets 'lab-logo.png'))
try {
    # 48 DIP at common Windows scaling factors, plus a compact 36 px export.
    foreach ($size in @(36,48,60,72,96,120,144,192)) {
        $bitmap = [Drawing.Bitmap]::new($size,$size,[Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $graphics = [Drawing.Graphics]::FromImage($bitmap)
        $attributes = [Drawing.Imaging.ImageAttributes]::new()
        try {
            $graphics.Clear([Drawing.Color]::Transparent)
            $graphics.CompositingMode = [Drawing.Drawing2D.CompositingMode]::SourceCopy
            $graphics.CompositingQuality = [Drawing.Drawing2D.CompositingQuality]::HighQuality
            $graphics.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.PixelOffsetMode = [Drawing.Drawing2D.PixelOffsetMode]::HighQuality
            $attributes.SetWrapMode([Drawing.Drawing2D.WrapMode]::TileFlipXY)
            $scale = [Math]::Min($size / $source.Width, $size / $source.Height)
            $width = [int][Math]::Round($source.Width * $scale)
            $height = [int][Math]::Round($source.Height * $scale)
            $destination = [Drawing.Rectangle]::new([int](($size-$width)/2),[int](($size-$height)/2),$width,$height)
            $graphics.DrawImage($source,$destination,0,0,$source.Width,$source.Height,[Drawing.GraphicsUnit]::Pixel,$attributes)
            $bitmap.Save((Join-Path $output "lab-logo-$size.png"),[Drawing.Imaging.ImageFormat]::Png)
        } finally {
            $attributes.Dispose(); $graphics.Dispose(); $bitmap.Dispose()
        }
    }
} finally { $source.Dispose() }
