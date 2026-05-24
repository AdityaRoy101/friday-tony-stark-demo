param(
  [switch]$UseDocker,
  [string]$BindAddress = "127.0.0.1",
  [int]$HttpPort = 7880,
  [int]$TcpPort = 7881,
  [int]$UdpPort = 7882
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BundledServer = Join-Path $RepoRoot "tools\livekit-server\livekit-server.exe"

Write-Output "Starting LiveKit local dev server..."
Write-Output "URL:        ws://127.0.0.1:$HttpPort"
Write-Output "API key:    devkey"
Write-Output "API secret: secret"
Write-Output ""

if (-not $UseDocker) {
  $LiveKitArgs = @(
    "--dev",
    "--bind", $BindAddress,
    "--port", "$HttpPort",
    "--rtc.tcp_port", "$TcpPort",
    "--udp-port", "$UdpPort"
  )

  if (Test-Path $BundledServer) {
    & $BundledServer @LiveKitArgs
    exit $LASTEXITCODE
  }

  $GlobalServer = Get-Command livekit-server -ErrorAction SilentlyContinue
  if ($GlobalServer) {
    & $GlobalServer.Source @LiveKitArgs
    exit $LASTEXITCODE
  }
}

$Docker = Get-Command docker -ErrorAction SilentlyContinue
if ($Docker) {
  docker run --rm -it `
    --name friday-livekit-local `
    -p "${HttpPort}:${HttpPort}" `
    -p "${TcpPort}:${TcpPort}" `
    -p "${UdpPort}:${UdpPort}/udp" `
    livekit/livekit-server:latest `
    --dev `
    --bind 0.0.0.0 `
    --port $HttpPort `
    --rtc.tcp_port $TcpPort `
    --udp-port $UdpPort
  exit $LASTEXITCODE
}

throw @"
LiveKit server was not found.

Install it into this repo with:
  scripts\install-livekit-server-windows.ps1

Then start it with:
  scripts\start-livekit-local.ps1
"@
