<#
.SYNOPSIS
    launch_multi_windows.ps1 -- Launch CloudflareAuto multi-worker sessions on Windows
.DESCRIPTION
    Mirrors the launch_multi_mac.sh and launch_multi_linux.sh workflow for Windows:
      - Automatically detects display resolution and working area (taskbar aware).
      - Arranges terminal windows into a tiled grid across the desktop.
      - Staggers launch startup delays (~30s apart) to avoid rate-limiting.
      - Executes main.py in continuous loop mode with safe rate-limit cooldowns.
      - Supports 'stop' action to terminate all running workers.
.EXAMPLE
    .\launch_multi_windows.ps1
    .\launch_multi_windows.ps1 -Action stop
    .\launch_multi_windows.ps1 -NumWindows 6 -Mode direct
#>

[CmdletBinding()]
param(
    [string]$Action = "start",
    [int]$NumWindows = 5,
    [string]$Mode = "direct",
    [string]$TargetUrl = "",
    [int]$DelayMin = 60,
    [int]$DelayMax = 120,
    [string]$Account = ""
)

# Ensure UTF-8 output encoding in PowerShell console
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir
$TmpDirWorkers = Join-Path $env:TEMP "cloudflare_auto_workers"

# Referral Account Presets
$Account1Url = "https://websurfer.1024tenbox.com/referral/XWUPKX2D"
$Account1Email = "pn@gmail.com"

$Account2Url = "https://websurfer.1024tenbox.com/referral/XUMZDQ5R"
$Account2Email = "dd@gmail.com"

$Account3Url = "https://websurfer.1024tenbox.com/referral/75H3QGGK"
$Account3Email = "jn@gmail.com"

# ── Stop Command ─────────────────────────────────────────────
if ($Action -eq "stop" -or $args -contains "stop") {
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "  Stopping all CloudflareAuto workers on Windows..." -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan

    # Terminate worker cmd processes by window title
    try {
        & taskkill.exe /F /FI "WINDOWTITLE eq Worker-*" 2>$null | Out-Null
    } catch {}

    # Terminate python.exe processes executing main.py
    try {
        Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*main.py*" } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    } catch {}

    # Clean up worker batch files and screenshots
    if (Test-Path $TmpDirWorkers) {
        Remove-Item -Path $TmpDirWorkers -Recurse -Force -ErrorAction SilentlyContinue
    }
    $tempScreenshots = Join-Path $env:TEMP "websurfer_screenshots"
    if (Test-Path $tempScreenshots) {
        Remove-Item -Path $tempScreenshots -Recurse -Force -ErrorAction SilentlyContinue
    }

    Write-Host "  [+] All CloudflareAuto workers stopped." -ForegroundColor Green
    Write-Host "================================================================" -ForegroundColor Cyan
    exit 0
}

# ── Account Selection ────────────────────────────────────────
$RoundRobin = $false
$TargetEmail = ""

# Handle parameter overrides if passed
if ($Account -eq "1" -or $Account -eq "pn" -or $Account -eq "pn@gmail.com") {
    $TargetUrl = $Account1Url
    $TargetEmail = $Account1Email
} elseif ($Account -eq "2" -or $Account -eq "dd" -or $Account -eq "dd@gmail.com") {
    $TargetUrl = $Account2Url
    $TargetEmail = $Account2Email
} elseif ($Account -eq "3" -or $Account -eq "jn" -or $Account -eq "jn@gmail.com") {
    $TargetUrl = $Account3Url
    $TargetEmail = $Account3Email
} elseif ($Account -eq "5" -or $Account -eq "all" -or $Account -eq "distribute" -or $Account -eq "round-robin") {
    $RoundRobin = $true
    $TargetEmail = "Round-Robin ($Account1Email, $Account2Email, $Account3Email)"
    $TargetUrl = "Distributed across 3 accounts"
} elseif ($TargetUrl -ne "" -and $TargetUrl -match "^https?://") {
    $TargetEmail = "Custom URL"
} else {
    # Interactive prompt if running in interactive PowerShell
    $isInteractive = $Host.UI.RawUI -ne $null -and [Environment]::UserInteractive
    if ($isInteractive) {
        Write-Host "================================================================" -ForegroundColor Cyan
        Write-Host "   CloudflareAuto -- Select Target Referral Account" -ForegroundColor Cyan
        Write-Host "================================================================" -ForegroundColor Cyan
        Write-Host "  [1] $Account1Email  ->  $Account1Url"
        Write-Host "  [2] $Account2Email  ->  $Account2Url  (Default Windows)"
        Write-Host "  [3] $Account3Email  ->  $Account3Url"
        Write-Host "  [4] Custom URL    ->  [Enter your own referral link]"
        Write-Host "  [5] Distribute    ->  Round-Robin across workers (Farms all accounts simultaneously)"
        Write-Host "================================================================" -ForegroundColor Cyan
        $choice = Read-Host "Select option [1-5, Enter for default 2]"
        if ([string]::IsNullOrWhiteSpace($choice)) { $choice = "2" }

        switch ($choice.Trim().ToLower()) {
            "1" {
                $TargetUrl = $Account1Url
                $TargetEmail = $Account1Email
            }
            "3" {
                $TargetUrl = $Account3Url
                $TargetEmail = $Account3Email
            }
            "4" {
                $customInput = Read-Host "Enter custom referral URL"
                if ([string]::IsNullOrWhiteSpace($customInput)) {
                    $TargetUrl = $Account2Url
                    $TargetEmail = $Account2Email
                } else {
                    $TargetUrl = $customInput.Trim()
                    $TargetEmail = "Custom Account"
                }
            }
            "5" {
                $RoundRobin = $true
                $TargetEmail = "Round-Robin ($Account1Email, $Account2Email, $Account3Email)"
                $TargetUrl = "Distributed across 3 accounts"
            }
            default {
                $TargetUrl = $Account2Url
                $TargetEmail = $Account2Email
            }
        }
    } else {
        $TargetUrl = $Account2Url
        $TargetEmail = $Account2Email
    }
}

# ── Clean up & prepare worker directory and screenshots ──────
if (Test-Path $TmpDirWorkers) {
    Remove-Item -Path $TmpDirWorkers -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path $TmpDirWorkers -Force | Out-Null
$tempScreenshots = Join-Path $env:TEMP "websurfer_screenshots"
if (Test-Path $tempScreenshots) {
    Remove-Item -Path $tempScreenshots -Recurse -Force -ErrorAction SilentlyContinue
}

# ── Virtual environment detection ───────────────────────────
$Python = "python"
if (Test-Path "$ProjectDir\.venv\Scripts\python.exe") {
    $Python = "$ProjectDir\.venv\Scripts\python.exe"
} elseif (Test-Path "$ProjectDir\venv\Scripts\python.exe") {
    $Python = "$ProjectDir\venv\Scripts\python.exe"
}

# ── Screen & Grid Geometry ───────────────────────────────────
Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue

$ScreenW = 1920
$ScreenH = 1080
$StartX = 0
$StartY = 0

try {
    $primary = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
    $ScreenW = $primary.Width
    $ScreenH = $primary.Height
    $StartX = $primary.X
    $StartY = $primary.Y
} catch {
    # Fallback to defaults
}

if ($NumWindows -le 3) {
    $Cols = $NumWindows
    $Rows = 1
} elseif ($NumWindows -le 6) {
    $Cols = 3
    $Rows = 2
} elseif ($NumWindows -le 8) {
    $Cols = 4
    $Rows = 2
} else {
    $Cols = 5
    $Rows = [math]::Ceiling($NumWindows / $Cols)
}

$Margin = 8
$TaskbarOffset = 5

$UsableW = $ScreenW - (($Cols + 1) * $Margin)
$UsableH = $ScreenH - $TaskbarOffset - (($Rows + 1) * $Margin)

$WinW = [math]::Floor($UsableW / $Cols)
$WinH = [math]::Floor($UsableH / $Rows)

# ── Win32 API for moving/sizing console windows ──────────────
if (-not ([System.Management.Automation.PSTypeName]'Win32Window').Type) {
    Add-Type @"
    using System;
    using System.Runtime.InteropServices;
    public class Win32Window {
        [DllImport("user32.dll", SetLastError = true)]
        public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);
        
        [DllImport("user32.dll", SetLastError = true)]
        public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);

        [DllImport("user32.dll")]
        public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    }
"@
}

# ── Banner ───────────────────────────────────────────────────
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "   CloudflareAuto -- Windows Multi-Session Launcher" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Project   : $ProjectDir"
Write-Host "  Python    : $Python"
Write-Host "  Mode      : $Mode (--loop)"
Write-Host "  Workers   : $NumWindows ($($Cols)x$($Rows) grid)"
Write-Host "  Screen    : $($ScreenW)x$($ScreenH) -> each win $($WinW)x$($WinH)"
Write-Host "  Pacing    : $DelayMin-$DelayMax`s (1-2 min) between runs"
Write-Host "  Target    : $TargetEmail"
if (-not $RoundRobin) {
    Write-Host "  URL       : $TargetUrl"
}
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# ── Generate Worker Scripts ──────────────────────────────────
$Rng = New-Object System.Random

for ($i = 0; $i -lt $NumWindows; $i++) {
    $num = "{0:D2}" -f ($i + 1)
    $label = "Worker-$num"
    $workerScript = Join-Path $TmpDirWorkers "worker_$num.bat"

    $col = $i % $Cols
    $row = [math]::Floor($i / $Cols)
    $x = $StartX + $Margin + ($col * ($WinW + $Margin))
    $y = $StartY + $TaskbarOffset + $Margin + ($row * ($WinH + $Margin))

    # Stagger launch start times (~30s intervals: Worker 1: ~10s, Worker 2: ~40s, Worker 3: ~70s, Worker 4: ~100s, Worker 5: ~130s)
    $baseDelay = $i * 30
    $jitter = $Rng.Next(5, 16)
    $delay = $baseDelay + $jitter

    # Assign worker target URL (round-robin or single selection)
    if ($RoundRobin) {
        $accounts = @($Account1Url, $Account2Url, $Account3Url)
        $emails = @($Account1Email, $Account2Email, $Account3Email)
        $idx = $i % 3
        $wUrl = $accounts[$idx]
        $wEmail = $emails[$idx]
    } else {
        $wUrl = $TargetUrl
        $wEmail = $TargetEmail
    }

    $scriptContent = @"
@echo off
title $label
chcp 65001 >nul 2>&1
cd /d "$ProjectDir"

echo.
echo =============================================
echo   $label ($wEmail)
echo   Target URL : $wUrl
echo   Waiting ${delay}s before start
echo =============================================
timeout /t $delay /nobreak >nul

echo.
echo [$label] Starting automation loop (mode=$Mode)...
echo [$label] Referral Account: $wEmail
echo.

:loop_forever
"$Python" main.py --mode $Mode --loop --target-url "$wUrl" --delay-min $DelayMin --delay-max $DelayMax
echo.
echo [$label] Process exited -- restarting in 5s...
timeout /t 5 /nobreak >nul
goto loop_forever
"@
    Set-Content -Path $workerScript -Value $scriptContent -Encoding ASCII
    Write-Host "  [$label]  grid=($col,$row)  account=$wEmail  delay=${delay}s" -ForegroundColor Gray
}

Write-Host ""

# ── Launch and Arrange Windows in Tiled Grid ─────────────────
Write-Host "[*] Launching $NumWindows terminal windows arranged in a $($Cols)x$($Rows) grid..." -ForegroundColor Yellow

for ($i = 0; $i -lt $NumWindows; $i++) {
    $num = "{0:D2}" -f ($i + 1)
    $label = "Worker-$num"
    $workerScript = Join-Path $TmpDirWorkers "worker_$num.bat"

    $col = $i % $Cols
    $row = [math]::Floor($i / $Cols)
    $x = $StartX + $Margin + ($col * ($WinW + $Margin))
    $y = $StartY + $TaskbarOffset + $Margin + ($row * ($WinH + $Margin))

    # Launch worker in a separate console window
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k `"$workerScript`""

    # Reposition window into its exact grid slot
    Start-Sleep -Milliseconds 350
    for ($attempt = 0; $attempt -lt 15; $attempt++) {
        $hwnd = [Win32Window]::FindWindow($null, $label)
        if ($hwnd -ne [IntPtr]::Zero) {
            [Win32Window]::MoveWindow($hwnd, $x, $y, $WinW, $WinH, $true) | Out-Null
            break
        }
        Start-Sleep -Milliseconds 150
    }
}

# Final pass to ensure all windows are firmly snapped into the grid layout
Start-Sleep -Seconds 1
for ($i = 0; $i -lt $NumWindows; $i++) {
    $num = "{0:D2}" -f ($i + 1)
    $label = "Worker-$num"
    $col = $i % $Cols
    $row = [math]::Floor($i / $Cols)
    $x = $StartX + $Margin + ($col * ($WinW + $Margin))
    $y = $StartY + $TaskbarOffset + $Margin + ($row * ($WinH + $Margin))

    $hwnd = [Win32Window]::FindWindow($null, $label)
    if ($hwnd -ne [IntPtr]::Zero) {
        [Win32Window]::MoveWindow($hwnd, $x, $y, $WinW, $WinH, $true) | Out-Null
    }
}

Write-Host ""
Write-Host "  [+] All $NumWindows windows launched and arranged in a $($Cols)x$($Rows) grid." -ForegroundColor Green
Write-Host "  👉 To stop all workers at any time, run:" -ForegroundColor Cyan
Write-Host "     .\launch_multi_windows.bat stop" -ForegroundColor White
Write-Host ""
