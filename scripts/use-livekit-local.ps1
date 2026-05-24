param(
  [string]$LiveKitUrl = "ws://127.0.0.1:7880",
  [string]$ApiKey = "devkey",
  [string]$ApiSecret = "secret"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$EnvPath = Join-Path $RepoRoot ".env"
$ExamplePath = Join-Path $RepoRoot ".env.example"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

if (-not (Test-Path $EnvPath)) {
  if (-not (Test-Path $ExamplePath)) {
    throw "Could not find .env or .env.example."
  }
  Copy-Item -LiteralPath $ExamplePath -Destination $EnvPath
}

$BackupPath = Join-Path $RepoRoot ".env.livekit-cloud.$Timestamp.bak"
Copy-Item -LiteralPath $EnvPath -Destination $BackupPath -Force

function Set-EnvValue {
  param(
    [string[]]$Lines,
    [string]$Key,
    [string]$Value
  )

  $Pattern = "^\s*$([regex]::Escape($Key))\s*="
  $Found = $false
  $Updated = foreach ($Line in $Lines) {
    if ($Line -match $Pattern) {
      $Found = $true
      "$Key=$Value"
    } else {
      $Line
    }
  }

  if (-not $Found) {
    $Updated += "$Key=$Value"
  }

  return $Updated
}

function Update-EnvFile {
  param([string]$Path)

  $Lines = Get-Content -LiteralPath $Path
  $Lines = Set-EnvValue -Lines $Lines -Key "LIVEKIT_URL" -Value $LiveKitUrl
  $Lines = Set-EnvValue -Lines $Lines -Key "LIVEKIT_API_KEY" -Value $ApiKey
  $Lines = Set-EnvValue -Lines $Lines -Key "LIVEKIT_API_SECRET" -Value $ApiSecret
  Set-Content -LiteralPath $Path -Value $Lines -Encoding UTF8
}

Update-EnvFile -Path $EnvPath

$DesktopEnvPath = Join-Path $RepoRoot "desktop-ui\.env.local"
if (Test-Path $DesktopEnvPath) {
  Copy-Item -LiteralPath $DesktopEnvPath -Destination "$DesktopEnvPath.$Timestamp.bak" -Force
  Update-EnvFile -Path $DesktopEnvPath
  Write-Host "Updated desktop-ui\.env.local because it exists and overrides root .env."
}

Write-Host "LiveKit env is now local:"
Write-Host "  LIVEKIT_URL=$LiveKitUrl"
Write-Host "  LIVEKIT_API_KEY=$ApiKey"
Write-Host "  LIVEKIT_API_SECRET=secret"
Write-Host ""
Write-Host "Backed up previous root .env to:"
Write-Host "  $BackupPath"
