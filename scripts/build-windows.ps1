param([string]$OutputDirectory = "dist")
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $repo
& (Join-Path $PSScriptRoot 'build-app-icon.ps1')
& (Join-Path $PSScriptRoot 'build-lab-logos.ps1')
if (-not [IO.Path]::IsPathRooted($OutputDirectory)) { $OutputDirectory = Join-Path $repo $OutputDirectory }
if (-not $env:UV_PROJECT_ENVIRONMENT) {
    $env:UV_PROJECT_ENVIRONMENT = Join-Path $env:LOCALAPPDATA 'ICTHubPrinterBuild\venv'
}
uv sync --locked --group build --no-dev
if ($LASTEXITCODE -ne 0) { throw 'uv sync failed' }
$python = Join-Path $env:UV_PROJECT_ENVIRONMENT 'Scripts\python.exe'
$work = Join-Path $env:LOCALAPPDATA 'ICTHubPrinterBuild\work'
$payload = Join-Path $work 'payload'
& $python -m PyInstaller --noconfirm --clean --onefile --name ICTHubPrinter --paths src --collect-submodules uvicorn --collect-submodules hp_printer --distpath $payload --workpath $work --specpath $work src/hp_printer/windows_entry.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$backend = Join-Path $payload 'ICTHubPrinter.exe'
$project = Join-Path $repo 'windows/ICTHubPrinter.Setup/ICTHubPrinter.Setup.csproj'
$obj = Join-Path $env:LOCALAPPDATA 'ICTHubPrinterBuild\dotnet-obj\'
dotnet publish $project -c Release -r win-x64 --self-contained true -p:BackendPath="$backend" -p:BaseIntermediateOutputPath="$obj" -o $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw 'WPF installer build failed' }
$exe = Join-Path $OutputDirectory 'ICTHubPrinterSetup.exe'
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath (Join-Path $OutputDirectory 'SHA256SUMS.txt') -Value "$hash  ICTHubPrinterSetup.exe" -Encoding ascii
Write-Output "Built graphical installer: $exe"
