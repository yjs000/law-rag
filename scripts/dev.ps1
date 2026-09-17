param(
    [switch]$Service,
    [string]$WorkingDirectory,
    [string]$LogPath,
    [string]$Label,
    [string]$ServiceCommandLine,
    [string]$StatusPath
)

if ($Service) {
    # Windows PowerShell represents native stderr as ErrorRecord objects. Keep
    # those records in the normal output pipeline so they are logged and shown.
    $ErrorActionPreference = "Continue"
    Push-Location $WorkingDirectory
    $serviceExitCode = 1
    try {
        & cmd.exe /d /s /c $ServiceCommandLine 2>&1 | ForEach-Object {
            $line = $_.ToString()
            Add-Content -LiteralPath $LogPath -Value $line -Encoding utf8 -ErrorAction Stop
            Write-Output "[$Label] $line"
        }
        $serviceExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
        Set-Content -LiteralPath $StatusPath -Value $serviceExitCode -Encoding ascii -NoNewline
    }
    exit $serviceExitCode
}

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$logDirectory = Join-Path $repoRoot "logs"
$apiLog = Join-Path $logDirectory "api.log"
$frontendLog = Join-Path $logDirectory "frontend.log"
$apiStatus = Join-Path $logDirectory ".api.exit"
$frontendStatus = Join-Path $logDirectory ".frontend.exit"

New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
Remove-Item -LiteralPath $apiStatus, $frontendStatus -Force -ErrorAction SilentlyContinue
$startedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss K"
Add-Content -LiteralPath $apiLog -Value "`n=== local dev started $startedAt ===" -Encoding utf8
Add-Content -LiteralPath $frontendLog -Value "`n=== local dev started $startedAt ===" -Encoding utf8

function ConvertTo-SingleQuotedArgument {
    param([string]$Value)

    return "'" + $Value.Replace("'", "''") + "'"
}

function Start-LoggedService {
    param(
        [string]$ServiceLabel,
        [string]$ServiceLogPath,
        [string]$ServiceStatusPath,
        [string]$CommandLine
    )

    $serviceInvocation = @(
        "& $(ConvertTo-SingleQuotedArgument $PSCommandPath)",
        "-Service",
        "-WorkingDirectory $(ConvertTo-SingleQuotedArgument $repoRoot)",
        "-LogPath $(ConvertTo-SingleQuotedArgument $ServiceLogPath)",
        "-Label $(ConvertTo-SingleQuotedArgument $ServiceLabel)",
        "-ServiceCommandLine $(ConvertTo-SingleQuotedArgument $CommandLine)",
        "-StatusPath $(ConvertTo-SingleQuotedArgument $ServiceStatusPath)"
    ) -join " "
    $childCommand = '$ProgressPreference = ''SilentlyContinue''; ' + $serviceInvocation
    $encodedCommand = [Convert]::ToBase64String(
        [Text.Encoding]::Unicode.GetBytes($childCommand)
    )

    return Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand $encodedCommand" `
        -NoNewWindow -PassThru
}

function Stop-ProcessTree {
    param([System.Diagnostics.Process]$Process)

    if (-not $Process.HasExited) {
        & cmd.exe /d /c "taskkill /PID $($Process.Id) /T /F >nul 2>&1"
    }
}

function Get-ServiceExitCode {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$ServiceStatusPath
    )

    if (-not $Process.HasExited) {
        return $null
    }
    $Process.WaitForExit()
    if (-not (Test-Path -LiteralPath $ServiceStatusPath)) {
        return 1
    }
    return [int](Get-Content -LiteralPath $ServiceStatusPath -Raw)
}

$processes = [Collections.Generic.List[Diagnostics.Process]]::new()
$statusPaths = @($apiStatus, $frontendStatus)

try {
    $processes.Add((
        Start-LoggedService -ServiceLabel "api" -ServiceLogPath $apiLog `
            -ServiceStatusPath $apiStatus `
            -CommandLine "uv run --project apps/api uvicorn app.main:app --app-dir apps/api --reload --port 8000"
    ))
    $processes.Add((
        Start-LoggedService -ServiceLabel "frontend" -ServiceLogPath $frontendLog `
            -ServiceStatusPath $frontendStatus `
            -CommandLine "pnpm run dev:web"
    ))

    Write-Host "API and frontend started. Logs: $logDirectory"
    Write-Host "Press Ctrl+C to stop both processes."

    while (@($processes | Where-Object { -not $_.HasExited }).Count -eq $processes.Count) {
        Start-Sleep -Milliseconds 100
    }

    $failedExitCode = $null
    for ($index = 0; $index -lt $processes.Count; $index++) {
        $exitCode = Get-ServiceExitCode $processes[$index] $statusPaths[$index]
        if ($null -ne $exitCode -and $exitCode -ne 0) {
            $failedExitCode = $exitCode
            break
        }
    }
    if ($null -eq $failedExitCode) {
        $processes | Where-Object { -not $_.HasExited } |
            Wait-Process -Timeout 1 -ErrorAction SilentlyContinue
        for ($index = 0; $index -lt $processes.Count; $index++) {
            $exitCode = Get-ServiceExitCode $processes[$index] $statusPaths[$index]
            if ($null -ne $exitCode -and $exitCode -ne 0) {
                $failedExitCode = $exitCode
                break
            }
        }
    }

    if ($null -ne $failedExitCode) {
        throw "Local dev process failed with exit code $failedExitCode"
    }
}
finally {
    foreach ($process in $processes) {
        Stop-ProcessTree $process
    }
    Remove-Item -LiteralPath $statusPaths -Force -ErrorAction SilentlyContinue
}
