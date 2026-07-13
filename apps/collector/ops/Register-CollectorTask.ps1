param(
    [string]$TaskName = "LawRag-Weekly-History-Sync",
    [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\.."))
)

$ErrorActionPreference = "Stop"
$invokeScript = Join-Path $RepositoryRoot "apps\collector\ops\Invoke-Collector.ps1"
$powershell = (Get-Process -Id $PID).Path
$arguments = '-NoProfile -NonInteractive -File "{0}" -Command sync-history -RepositoryRoot "{1}"' -f $invokeScript, $RepositoryRoot
$action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory $RepositoryRoot
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "03:17"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Law Open API history sync from first effective version" `
    -Force

Write-Host "Registered: $TaskName (Sunday 03:17)"
