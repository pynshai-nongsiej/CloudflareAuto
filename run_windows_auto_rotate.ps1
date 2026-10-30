<#
.SYNOPSIS
    run_windows_auto_rotate.ps1 -- 6-Worker Auto-Rotator & Dashboard for Windows
#>
[CmdletBinding()]
param(
    [int]$NumWorkers = 6,
    [string]$Mode = "direct",
    [int]$DelayMin = 0,
    [int]$DelayMax = 0,
    [switch]$Headless,
    [switch]$BrowserHeaded,
    [string]$Country = "",
    [int]$CooldownMin = 45,
    [int]$CooldownMax = 60
)

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

$Python = "python"
if (Test-Path "$ProjectDir\.venv\Scripts\python.exe") {
    $Python = "$ProjectDir\.venv\Scripts\python.exe"
} elseif (Test-Path "$ProjectDir\venv\Scripts\python.exe") {
    $Python = "$ProjectDir\venv\Scripts\python.exe"
}

$argsList = @(
    "$ProjectDir\rotate_and_run_windows.py",
    "--num-workers", $NumWorkers,
    "--mode", $Mode,
    "--delay-min", $DelayMin,
    "--delay-max", $DelayMax,
    "--cooldown-min", $CooldownMin,
    "--cooldown-max", $CooldownMax
)
if ($Headless) { $argsList += "--headless" }
if ($BrowserHeaded) { $argsList += "--browser-headed" }
if ($Country) { $argsList += @("--country", $Country) }

& $Python $argsList
