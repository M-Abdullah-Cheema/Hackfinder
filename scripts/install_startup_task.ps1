# Register QuestHub backend to start at Windows logon (no admin required).
# Uses the user Startup folder instead of Task Scheduler.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\install_startup_task.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$StartScript = Join-Path $Root "scripts\start_backend.ps1"
$StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$CmdPath = Join-Path $StartupDir "QuestHubBackend.cmd"

if (-not (Test-Path $StartScript)) {
    throw "Missing $StartScript"
}
if (-not (Test-Path $StartupDir)) {
    New-Item -ItemType Directory -Path $StartupDir -Force | Out-Null
}

$cmd = @"
@echo off
cd /d "$Root"
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "$StartScript"
"@

Set-Content -Path $CmdPath -Value $cmd -Encoding ASCII
Write-Host "[OK] Startup shortcut created:" -ForegroundColor Green
Write-Host "     $CmdPath"
Write-Host "     QuestHub backend will start when you log into Windows."
Write-Host "     Test now: powershell -ExecutionPolicy Bypass -File `"$StartScript`""
Write-Host ""
Write-Host "To remove later, delete: $CmdPath"
