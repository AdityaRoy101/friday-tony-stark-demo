param(
  [switch]$Force
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$InstallDir = Join-Path $RepoRoot "tools\livekit-server"
$ExePath = Join-Path $InstallDir "livekit-server.exe"

if ((Test-Path $ExePath) -and -not $Force) {
  Write-Host "LiveKit server is already installed at $ExePath"
  Write-Host "Use -Force to reinstall."
  exit 0
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

$Release = Invoke-RestMethod `
  -Uri "https://api.github.com/repos/livekit/livekit/releases/latest" `
  -Headers @{ "User-Agent" = "friday-local-livekit-setup" }

$Asset = $Release.assets |
  Where-Object { $_.name -match "windows_amd64\.zip$" } |
  Select-Object -First 1

if (-not $Asset) {
  throw "Could not find a Windows AMD64 LiveKit server asset in the latest GitHub release."
}

$ZipPath = Join-Path $env:TEMP $Asset.name
$ExtractDir = Join-Path $env:TEMP ("friday-livekit-" + [guid]::NewGuid().ToString("N"))

Write-Host "Downloading $($Asset.name) from LiveKit $($Release.tag_name)..."
Invoke-WebRequest -Uri $Asset.browser_download_url -OutFile $ZipPath

New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null
Expand-Archive -LiteralPath $ZipPath -DestinationPath $ExtractDir -Force

$DownloadedExe = Get-ChildItem -Path $ExtractDir -Recurse -Filter "livekit-server.exe" |
  Select-Object -First 1

if (-not $DownloadedExe) {
  throw "Downloaded archive did not contain livekit-server.exe."
}

Copy-Item -LiteralPath $DownloadedExe.FullName -Destination $ExePath -Force
Remove-Item -LiteralPath $ZipPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $ExtractDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Installed LiveKit server:"
& $ExePath --version
Write-Host ""
Write-Host "Start local LiveKit with:"
Write-Host "  scripts\start-livekit-local.ps1"
