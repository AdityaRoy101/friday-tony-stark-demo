param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$DesktopUiRoot = Join-Path $RepoRoot "desktop-ui"
$LogDir = Join-Path $RepoRoot "logs"
$ServiceNames = @("friday-desktop-ui", "friday-voice", "friday-mcp", "livekit-local")

function Get-ChildProcessIds {
    param([int]$ParentProcessId)

    $children = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $ParentProcessId }
    foreach ($child in $children) {
        Get-ChildProcessIds -ParentProcessId ([int]$child.ProcessId)
        [int]$child.ProcessId
    }
}

function Stop-ProcessTree {
    param(
        [int]$ProcessId,
        [string]$Name
    )

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $process) {
        Write-Host "$Name is not running (pid $ProcessId)."
        return
    }

    $processIds = @()
    $processIds += Get-ChildProcessIds -ParentProcessId $ProcessId
    $processIds += $ProcessId
    $processIds = $processIds | Where-Object { $_ } | Select-Object -Unique

    foreach ($id in $processIds) {
        $target = Get-Process -Id $id -ErrorAction SilentlyContinue
        if (-not $target) {
            continue
        }

        if ($DryRun) {
            Write-Host "Dry run: would stop $($target.ProcessName) pid $id for $Name"
        }
        else {
            Write-Host "Stopping $($target.ProcessName) pid $id for $Name"
            Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
        }
    }
}

function Test-ContainsPath {
    param(
        [string]$CommandLine,
        [string]$Path
    )

    if (-not $CommandLine -or -not $Path) {
        return $false
    }

    return $CommandLine.IndexOf($Path, [StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Stop-StaleStackProcesses {
    $processes = @(Get-CimInstance Win32_Process)
    $processById = @{}
    foreach ($process in $processes) {
        $processById[[int]$process.ProcessId] = $process
    }

    $stackMarkers = @(
        (Join-Path $RepoRoot "tools\livekit-server\livekit-server.exe"),
        (Join-Path $RepoRoot ".venv\Scripts\friday_voice.exe"),
        (Join-Path $RepoRoot ".venv\Scripts\friday.exe"),
        (Join-Path $DesktopUiRoot "node_modules\electron"),
        (Join-Path $DesktopUiRoot "node_modules\electron-vite"),
        (Join-Path $DesktopUiRoot "node_modules\.bin"),
        $DesktopUiRoot
    )

    $matchedIds = New-Object "System.Collections.Generic.HashSet[int]"
    foreach ($process in $processes) {
        $commandLine = [string]$process.CommandLine
        if (-not $commandLine) {
            continue
        }

        $isFridayProcess = $false
        foreach ($marker in $stackMarkers) {
            if (Test-ContainsPath -CommandLine $commandLine -Path $marker) {
                $isFridayProcess = $true
                break
            }
        }

        if (-not $isFridayProcess) {
            continue
        }

        [void]$matchedIds.Add([int]$process.ProcessId)

        $parentId = [int]$process.ParentProcessId
        if ($processById.ContainsKey($parentId)) {
            $parentCommandLine = [string]$processById[$parentId].CommandLine
            if ($parentCommandLine -match 'uv(\.exe)?\"?\s+run\s+friday(_voice)?' -or $parentCommandLine -match 'electron-vite\s+dev') {
                [void]$matchedIds.Add($parentId)
            }
        }
    }

    $rootIds = New-Object "System.Collections.Generic.HashSet[int]"
    foreach ($id in $matchedIds) {
        $currentId = [int]$id
        $hasMatchedAncestor = $false
        while ($processById.ContainsKey($currentId)) {
            $parentId = [int]$processById[$currentId].ParentProcessId
            if ($matchedIds.Contains($parentId)) {
                $hasMatchedAncestor = $true
                break
            }
            if ($parentId -le 0 -or -not $processById.ContainsKey($parentId)) {
                break
            }
            $currentId = $parentId
        }

        if (-not $hasMatchedAncestor) {
            [void]$rootIds.Add([int]$id)
        }
    }

    foreach ($id in ($rootIds | Sort-Object -Unique)) {
        Stop-ProcessTree -ProcessId $id -Name "stale Friday stack process"
    }
}

if (-not (Test-Path -LiteralPath $LogDir)) {
    Write-Host "No logs directory found at $LogDir."
    exit 0
}

foreach ($name in $ServiceNames) {
    $pidPath = Join-Path $LogDir "$name.pid"
    if (-not (Test-Path -LiteralPath $pidPath)) {
        Write-Host "No pid file for $name."
        continue
    }

    $rawPid = (Get-Content -LiteralPath $pidPath -Raw).Trim()
    $pidValue = 0
    if (-not [int]::TryParse($rawPid, [ref]$pidValue)) {
        Write-Host "Invalid pid file for $name`: $pidPath"
        continue
    }

    Stop-ProcessTree -ProcessId $pidValue -Name $name
    if (-not $DryRun) {
        Remove-Item -LiteralPath $pidPath -ErrorAction SilentlyContinue
    }
}

Stop-StaleStackProcesses

Write-Host "Friday stack stop requested."
