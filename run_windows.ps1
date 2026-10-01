<#
.SYNOPSIS
    TenBox Websurfer Auto-Registration launcher for Windows PowerShell.
.DESCRIPTION
    Launches TenBox registration automation in virtualenv with full Windows support.
.EXAMPLE
    .\run_windows.ps1
    .\run_windows.ps1 -Mode direct -Headed
    .\run_windows.ps1 -Mode direct -Loop -Count 5
#>

[CmdletBinding()]
param(
    [string]$Mode = "direct",
    [switch]$Headed,
    [switch]$Loop,
    [int]$Count = 0,
    [int]$DelayMin = 60,
    [int]$DelayMax = 120,
    [string]$Provider = "",
    [string]$Model = ""
)

$ErrorActionPreference = "Stop"

# Ensure UTF-8 output encoding in PowerShell console
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Check virtual environment
$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "[X] Virtual environment not found at .venv" -ForegroundColor Red
    Write-Host "[*] Please run .\setup_windows.bat first to install dependencies." -ForegroundColor Yellow
    exit 1
}

# Build arguments list
$PyArgs = @("main.py", "--mode", $Mode)

if ($Headed) {
    $PyArgs += "--headed"
}

if ($Loop) {
    $PyArgs += "--loop"
    if ($Count -gt 0) {
        $PyArgs += @("--count", $Count.ToString())
    }
    $PyArgs += @("--delay-min", $DelayMin.ToString(), "--delay-max", $DelayMax.ToString())
}

if ($Provider) {
    $PyArgs += @("--provider", $Provider)
}

if ($Model) {
    $PyArgs += @("--model", $Model)
}

# Forward any extra unbound arguments
if ($args.Count -gt 0) {
    $PyArgs += $args
}

Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "                TenBox Websurfer Automation (PowerShell)" -ForegroundColor Cyan
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "[*] Running: $VenvPython $($PyArgs -join ' ')" -ForegroundColor DarkGray
Write-Host ""

& $VenvPython $PyArgs
