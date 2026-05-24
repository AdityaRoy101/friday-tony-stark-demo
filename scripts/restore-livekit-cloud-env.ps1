param(
  [string]$BackupPath
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$EnvPath = Join-Path $RepoRoot ".env"

if (-not $BackupPath) {
  $BackupPath = Get-ChildItem -Path $RepoRoot -Filter ".env.livekit-cloud.*.bak" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1 |
    ForEach-Object { $_.FullName }
}

if (-not $BackupPath -or -not (Test-Path $BackupPath)) {
  throw "No LiveKit Cloud env backup found. Pass -BackupPath explicitly."
}

Copy-Item -LiteralPath $BackupPath -Destination $EnvPath -Force
Write-Host "Restored root .env from:"
Write-Host "  $BackupPath"

$DesktopEnvPath = Join-Path $RepoRoot "desktop-ui\.env.local"
if (Test-Path $DesktopEnvPath) {
  Write-Host ""
  Write-Host "Note: desktop-ui\.env.local exists and may override root .env for the Electron app."
}
