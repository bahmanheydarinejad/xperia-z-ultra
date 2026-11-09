# ==============================================================================
# Deploy & Launch All-Module Diagnostic Kiosk App on Xperia Z Ultra
# ==============================================================================
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\deploy_diagnostic_app.ps1
# ==============================================================================

$ErrorActionPreference = "Stop"
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
$AdbExe = "$ProjectRoot\tools\platform-tools\adb.exe"
$AppDir = "$ProjectRoot\modular_apps\hardware_test_app"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "   Deploying All-Module Hardware Diagnostic Kiosk App to Phone   " -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Check ADB
$devices = & $AdbExe devices
if ($devices -notmatch "device\b") {
    Write-Host "[-] Error: Device not detected via ADB." -ForegroundColor Red
    exit 1
}

# 2. Package App Payload
Write-Host "[1/4] Packaging modular application payload..." -ForegroundColor Yellow
$tarArchive = "$ProjectRoot\downloads\hardware_test_app.tar.gz"
if (Test-Path $tarArchive) { Remove-Item $tarArchive -Force }

# Use tar to archive
tar -czf "$tarArchive" -C "$AppDir" .
Write-Host "[+] Application packaged into $tarArchive" -ForegroundColor Green

# 3. Push to Device
Write-Host "[2/4] Pushing application archive to phone storage..." -ForegroundColor Yellow
& $AdbExe push "$tarArchive" "/sdcard/hardware_test_app.tar.gz"

# 4. Wipe Old App Section & Install Pristine App Payload
Write-Host "[3/4] Wiping /opt/app slot and installing new diagnostic payload..." -ForegroundColor Yellow
& $AdbExe shell "chroot /data/alpine /usr/local/bin/modular-app-mgr install /sdcard/hardware_test_app.tar.gz"

# 5. Launch Kiosk App (Boot into Fullscreen on FB0)
Write-Host "[4/4] Starting Kiosk App on screen..." -ForegroundColor Yellow
& $AdbExe shell "chroot /data/alpine /bin/sh -c 'nohup /usr/local/bin/kiosk_autostart.sh > /var/log/kiosk_supervisor.log 2>&1 &'"

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host " All-Module Diagnostic Kiosk App is now active on the phone screen!" -ForegroundColor Green
Write-Host " The phone display shows ONLY the live diagnostic kiosk dashboard." -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
