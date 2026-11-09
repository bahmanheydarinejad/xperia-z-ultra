# ==============================================================================
# Sony Xperia Z Ultra (togari) — Windows Host Wipe & Modular Base Installer
# ==============================================================================
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\wipe_and_init_base.ps1
# ==============================================================================

$ErrorActionPreference = "Stop"
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
$AdbExe = "$ProjectRoot\tools\platform-tools\adb.exe"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "    Xperia Z Ultra: Bare-Metal Clean Wipe & Modular Base Init    " -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Check ADB Connection
Write-Host "[1/5] Checking ADB device connection..." -ForegroundColor Yellow
$devices = & $AdbExe devices
if ($devices -notmatch "device\b") {
    Write-Host "[-] Error: Xperia Z Ultra not detected in ADB mode!" -ForegroundColor Red
    Write-Host "    Ensure USB debugging is enabled or phone is in TWRP recovery." -ForegroundColor Yellow
    exit 1
}
Write-Host "[+] Device detected." -ForegroundColor Green

# 2. Upload Base RootFS archive if needed
Write-Host "[2/5] Ensuring Alpine minirootfs archive is present on device..." -ForegroundColor Yellow
$localRootfs = "$ProjectRoot\downloads\alpine-minirootfs-3.20.3-armv7.tar.gz"
if (Test-Path $localRootfs) {
    & $AdbExe push $localRootfs /sdcard/alpine-minirootfs-3.20.3-armv7.tar.gz
    Write-Host "[+] Pushed Alpine rootfs to /sdcard/." -ForegroundColor Green
} else {
    Write-Host "[-] Warning: $localRootfs not found locally. Assuming already on device." -ForegroundColor Magenta
}

# 3. Push Wipe & Init Base Script
Write-Host "[3/5] Pushing wipe_and_init_base.sh to device..." -ForegroundColor Yellow
$deviceScript = "$PSScriptRoot\wipe_and_init_base.sh"
& $AdbExe push $deviceScript /data/wipe_and_init_base.sh
& $AdbExe shell "chmod +x /data/wipe_and_init_base.sh"

# 4. Execute Remote Wipe and Driver Initialization
Write-Host "[4/5] Executing wipe and low-level driver initialization on phone..." -ForegroundColor Yellow
& $AdbExe shell "sh /data/wipe_and_init_base.sh"

# 5. Success summary
Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host " Phone has been wiped and pristine driver layer is established!  " -ForegroundColor Green
Write-Host " Base drivers & OS:  /data/alpine (Alpine Linux ARMv7)           " -ForegroundColor Green
Write-Host " Modular App Slot:   /data/modular-app (Mounted at /opt/app)     " -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
