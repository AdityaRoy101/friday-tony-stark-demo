$ErrorActionPreference = "Stop"

$Result = Test-NetConnection -ComputerName "127.0.0.1" -Port 7880 -WarningAction SilentlyContinue

if ($Result.TcpTestSucceeded) {
  Write-Host "OK: Local LiveKit is reachable at ws://127.0.0.1:7880"
  exit 0
}

Write-Host "NOT READY: Local LiveKit is not reachable at ws://127.0.0.1:7880"
Write-Host "Start it with:"
Write-Host "  scripts\start-livekit-local.ps1"
exit 1
