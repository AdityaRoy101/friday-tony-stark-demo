param(
    [switch]$SkipLocalLiveKit,
    [switch]$SkipMcp,
    [switch]$SkipVoiceAgent,
    [switch]$SkipDesktopUi,
    [switch]$DryRun,
    [int]$LiveKitPort = 7880,
    [int]$LiveKitTcpPort = 7881,
    [int]$LiveKitUdpPort = 7882,
    [int]$LiveKitReadyTimeoutSeconds = 60,
    [int]$VoiceAgentReadyTimeoutSeconds = 75,
    [int]$McpPort = 8000,
    [int]$RendererPort = 5173
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$DesktopUiRoot = Join-Path $RepoRoot "desktop-ui"
$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Test-TcpPort {
    param(
        [string]$HostName,
        [int]$Port,
        [int]$TimeoutMs = 1200
    )

    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        $connected = $async.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if ($connected) {
            $client.EndConnect($async)
        }
        $client.Close()
        return $connected
    }
    catch {
        return $false
    }
}

function Start-LoggedProcess {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Command
    )

    $stdoutLogPath = Join-Path $LogDir "$Name.out.log"
    $stderrLogPath = Join-Path $LogDir "$Name.err.log"
    $pidPath = Join-Path $LogDir "$Name.pid"
    Remove-Item -LiteralPath $stdoutLogPath, $stderrLogPath, $pidPath -ErrorAction SilentlyContinue

    $quotedWorkingDirectory = "'" + ($WorkingDirectory -replace "'", "''") + "'"
    $script = @"
`$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $quotedWorkingDirectory
`$env:PYTHONUNBUFFERED = "1"
$Command
if (`$global:LASTEXITCODE -is [int]) {
    exit `$global:LASTEXITCODE
}
"@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))

    Write-Host "Starting $Name."
    Write-Host "  stdout: $stdoutLogPath"
    Write-Host "  stderr: $stderrLogPath"
    if ($DryRun) {
        Write-Host "Dry run: would execute in $WorkingDirectory -> $Command"
        return [pscustomobject]@{
            Name = $Name
            Process = $null
            Id = "dry-run"
            StdoutLog = $stdoutLogPath
            StderrLog = $stderrLogPath
            PidFile = $pidPath
        }
    }

    $process = Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encoded `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLogPath `
        -RedirectStandardError $stderrLogPath `
        -PassThru

    Set-Content -LiteralPath $pidPath -Value $process.Id -Encoding ASCII

    return [pscustomobject]@{
        Name = $Name
        Process = $process
        Id = $process.Id
        StdoutLog = $stdoutLogPath
        StderrLog = $stderrLogPath
        PidFile = $pidPath
    }
}

function Get-LogTailText {
    param(
        [string]$Path,
        [int]$Lines = 80
    )

    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) {
        return ""
    }

    $content = Get-Content -LiteralPath $Path -Tail $Lines -ErrorAction SilentlyContinue
    if (-not $content) {
        return ""
    }

    return ($content -join [Environment]::NewLine).TrimEnd()
}

function Get-ProcessLogSummary {
    param(
        $ProcessInfo
    )

    if (-not $ProcessInfo) {
        return "No process diagnostics were captured."
    }

    $stdout = Get-LogTailText -Path $ProcessInfo.StdoutLog
    $stderr = Get-LogTailText -Path $ProcessInfo.StderrLog
    $parts = @()

    if ($stdout) {
        $parts += "stdout tail ($($ProcessInfo.StdoutLog)):`n$stdout"
    }
    if ($stderr) {
        $parts += "stderr tail ($($ProcessInfo.StderrLog)):`n$stderr"
    }
    if ($parts.Count -eq 0) {
        $parts += "No log output captured yet. stdout=$($ProcessInfo.StdoutLog) stderr=$($ProcessInfo.StderrLog)"
    }

    return ($parts -join "`n`n")
}

function Get-ChildProcessIds {
    param(
        [int]$ParentProcessId
    )

    $children = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object ParentProcessId -eq $ParentProcessId)
    foreach ($child in $children) {
        Get-ChildProcessIds -ParentProcessId ([int]$child.ProcessId)
        [int]$child.ProcessId
    }
}

function Test-LoggedProcessRunning {
    param(
        [string]$PidPath,
        [string]$CommandPattern
    )

    if (-not (Test-Path -LiteralPath $PidPath)) {
        return $false
    }

    $rawPid = (Get-Content -LiteralPath $PidPath -Raw -ErrorAction SilentlyContinue).Trim()
    $processId = 0
    if (-not [int]::TryParse($rawPid, [ref]$processId)) {
        Remove-Item -LiteralPath $PidPath -ErrorAction SilentlyContinue
        return $false
    }

    $rootProcess = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $rootProcess) {
        Remove-Item -LiteralPath $PidPath -ErrorAction SilentlyContinue
        return $false
    }

    $treeProcessIds = @($processId) + @(Get-ChildProcessIds -ParentProcessId $processId)
    $matchingProcess = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $treeProcessIds -contains [int]$_.ProcessId -and $_.CommandLine -match $CommandPattern } |
        Select-Object -First 1

    if ($matchingProcess) {
        return $true
    }

    Remove-Item -LiteralPath $PidPath -ErrorAction SilentlyContinue
    return $false
}

function Wait-ForPort {
    param(
        [string]$Name,
        [int]$Port,
        [int]$TimeoutSeconds = 20,
        $ProcessInfo = $null
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-TcpPort -HostName "127.0.0.1" -Port $Port) {
            Write-Host "$Name is ready on 127.0.0.1:$Port"
            return
        }
        if ($ProcessInfo -and $ProcessInfo.Process -and $ProcessInfo.Process.HasExited) {
            $summary = Get-ProcessLogSummary -ProcessInfo $ProcessInfo
            throw "$Name exited before becoming ready on 127.0.0.1:$Port. Exit code: $($ProcessInfo.Process.ExitCode)`n`n$summary"
        }
        Start-Sleep -Milliseconds 500
    }

    $timeoutSummary = Get-ProcessLogSummary -ProcessInfo $ProcessInfo
    throw "$Name did not become ready on 127.0.0.1:$Port within $TimeoutSeconds seconds.`n`n$timeoutSummary"
}

function Wait-ForLogPattern {
    param(
        [string]$Name,
        [string]$LogPath,
        [string]$Pattern,
        [int]$TimeoutSeconds = 60,
        $ProcessInfo = $null
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ((Test-Path -LiteralPath $LogPath) -and (Select-String -LiteralPath $LogPath -Pattern $Pattern -Quiet -ErrorAction SilentlyContinue)) {
            Write-Host "$Name is ready."
            return
        }
        if ($ProcessInfo -and $ProcessInfo.Process -and $ProcessInfo.Process.HasExited) {
            $summary = Get-ProcessLogSummary -ProcessInfo $ProcessInfo
            throw "$Name exited before becoming ready. Exit code: $($ProcessInfo.Process.ExitCode)`n`n$summary"
        }
        Start-Sleep -Milliseconds 500
    }

    $timeoutSummary = Get-ProcessLogSummary -ProcessInfo $ProcessInfo
    throw "$Name did not become ready within $TimeoutSeconds seconds. Waiting for log pattern: $Pattern`n`n$timeoutSummary"
}

if (-not (Test-Path (Join-Path $RepoRoot ".env"))) {
    throw "Missing .env in $RepoRoot. Create it from .env.example first."
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is not installed or not on PATH."
}

if (-not $SkipDesktopUi -and -not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm is not installed or not on PATH."
}

$started = @()

if (-not $SkipLocalLiveKit) {
    if (-not (Test-TcpPort -HostName "127.0.0.1" -Port $LiveKitPort)) {
        $livekitProcess = Start-LoggedProcess `
            -Name "livekit-local" `
            -WorkingDirectory $RepoRoot `
            -Command "& .\scripts\start-livekit-local.ps1 -BindAddress 127.0.0.1 -HttpPort $LiveKitPort -TcpPort $LiveKitTcpPort -UdpPort $LiveKitUdpPort"
        $started += $livekitProcess
        if (-not $DryRun) {
            Wait-ForPort -Name "LiveKit" -Port $LiveKitPort -TimeoutSeconds $LiveKitReadyTimeoutSeconds -ProcessInfo $livekitProcess
        }
    }
    else {
        Write-Host "LiveKit is already running on 127.0.0.1:$LiveKitPort"
    }
}

if (-not $SkipMcp) {
    if (-not (Test-TcpPort -HostName "127.0.0.1" -Port $McpPort)) {
        $mcpProcess = Start-LoggedProcess `
            -Name "friday-mcp" `
            -WorkingDirectory $RepoRoot `
            -Command "uv run friday"
        $started += $mcpProcess
        if (-not $DryRun) {
            Wait-ForPort -Name "MCP server" -Port $McpPort -TimeoutSeconds 25 -ProcessInfo $mcpProcess
        }
    }
    else {
        Write-Host "MCP server is already running on 127.0.0.1:$McpPort"
    }
}
else {
    Write-Host "Skipping MCP server."
}

if (-not $SkipVoiceAgent) {
    $voicePidPath = Join-Path $LogDir "friday-voice.pid"
    if (Test-LoggedProcessRunning -PidPath $voicePidPath -CommandPattern "friday_voice|uv(.exe)?\s+run\s+friday_voice") {
        Write-Host "Friday voice agent is already running."
    }
    else {
        $voiceProcess = Start-LoggedProcess `
            -Name "friday-voice" `
            -WorkingDirectory $RepoRoot `
            -Command "uv run friday_voice"
        $started += $voiceProcess
        if (-not $DryRun) {
            Wait-ForLogPattern -Name "Friday voice agent" -LogPath $voiceProcess.StdoutLog -Pattern "registered worker" -TimeoutSeconds $VoiceAgentReadyTimeoutSeconds -ProcessInfo $voiceProcess
        }
    }
}
else {
    Write-Host "Skipping Friday voice agent."
}

if (-not $SkipDesktopUi) {
    if (-not (Test-Path (Join-Path $DesktopUiRoot "node_modules"))) {
        Write-Host "Installing desktop UI dependencies..."
        if (-not $DryRun) {
            Push-Location $DesktopUiRoot
            npm install
            Pop-Location
        }
    }

    if (-not (Test-TcpPort -HostName "127.0.0.1" -Port $RendererPort)) {
        $started += Start-LoggedProcess `
            -Name "friday-desktop-ui" `
            -WorkingDirectory $DesktopUiRoot `
            -Command "npm run dev"
    }
    else {
        Write-Host "Desktop renderer is already running on 127.0.0.1:$RendererPort"
    }
}

Write-Host ""
Write-Host "Friday stack launch requested."
Write-Host "Logs: $LogDir"
Write-Host "Processes started this run:"
$started | ForEach-Object { Write-Host "  $($_.Id) $($_.Name)" }
