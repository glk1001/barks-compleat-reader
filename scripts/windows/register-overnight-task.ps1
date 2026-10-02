# cspell:ignore waketimers
# Register the nightly Windows overnight run as a Task Scheduler task, so a second
# machine is set up the same way (docs/plans/windows-overnight.md, step 3).
#
# The task runs scripts/run_overnight_desktop.py through uv from this checkout:
#   - nightly at -At (default 02:00);
#   - "Run only when user is logged on" (an Interactive logon): SendInput needs the
#     interactive desktop, which a task run without a logged-on user does not have;
#   - "Wake the computer to run this task";
#   - "Stop the task if it runs longer than" 2 hours, in case a stage hangs;
#   - not started late when a night was missed: it would take over the machine
#     while someone uses it.
# `uv run --no-sync`: the run's update stage does the sync, in its own log.
#
# Usage (PowerShell, as the user the run should run as; no elevation needed):
#   powershell -ExecutionPolicy Bypass -File scripts\windows\register-overnight-task.ps1
#   ... -At 03:30          another time
#   ... -Unregister        remove the task
# Re-running replaces the task. Its results: build\overnight\<stamp>\summary.txt.
# To run it now, as the schedule would: Start-ScheduledTask -TaskName "Barks Reader overnight"

param(
    [string]$At = "02:00",
    [string]$TaskName = "Barks Reader overnight",
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"

if ($Unregister) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Output "Removed the task '$TaskName'."
    exit 0
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
    throw "uv is not on PATH: install it first (docs/setup.md)"
}

$action = New-ScheduledTaskAction -Execute $uv `
    -Argument "run --no-sync python scripts\run_overnight_desktop.py" `
    -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "The Barks Reader's nightly Windows run: docs/plans/windows-overnight.md" `
    -Force | Out-Null

Write-Output "Registered '$TaskName': nightly at $At, in $repo, through $uv."
Write-Output "Wake timers must be allowed in the power plan (powercfg /waketimers lists them)."
