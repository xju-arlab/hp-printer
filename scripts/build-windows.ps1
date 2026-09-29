param([string]$OutputDirectory = "dist")
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $repo
if (-not $env:UV_PROJECT_ENVIRONMENT) {
    $env:UV_PROJECT_ENVIRONMENT = Join-Path $env:LOCALAPPDATA 'ICTHubPrinterBuild\venv'
}
uv sync --locked --group build --no-dev
if ($LASTEXITCODE -ne 0) { throw 'uv sync failed' }
$python = Join-Path $env:UV_PROJECT_ENVIRONMENT 'Scripts\python.exe'
$work = Join-Path $env:LOCALAPPDATA 'ICTHubPrinterBuild\work'
& $python -m PyInstaller --noconfirm --clean --onefile --name ICTHubPrinterSetup --paths src --collect-submodules uvicorn --collect-submodules hp_printer --distpath $OutputDirectory --workpath $work --specpath $work src/hp_printer/windows_entry.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$exe = Join-Path $OutputDirectory 'ICTHubPrinterSetup.exe'
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath (Join-Path $OutputDirectory 'SHA256SUMS.txt') -Value "$hash  ICTHubPrinterSetup.exe" -Encoding ascii
& $exe --version
if ($LASTEXITCODE -ne 0) { throw 'Executable smoke check failed' }
