# ==============================================================================
# Deploy & Launch PS5 DualSense Controller Kiosk App on Xperia Z Ultra
# ==============================================================================
param (
    [switch]$Foreground = $false
)

$ErrorActionPreference = "Stop"
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
$AdbExe = "$ProjectRoot\tools\platform-tools\adb.exe"
$AppDir = "$ProjectRoot\modular_apps\ps5_controller_app"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "     Deploying PS5 Controller Kiosk App to Xperia Z Ultra        " -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Check ADB connection
$devicesOutput = (& $AdbExe devices | Out-String)
if ($devicesOutput -notmatch "(device|recovery)\b") {
    Write-Host "[-] Error: Device not detected via ADB." -ForegroundColor Red
    exit 1
}

# 2. Package Payload
Write-Host "[1/4] Packaging application payload..." -ForegroundColor Yellow
$tarArchive = "$ProjectRoot\downloads\ps5_controller_app.tar.gz"
if (Test-Path $tarArchive) { Remove-Item $tarArchive -Force }
tar -czf "$tarArchive" -C "$AppDir" .
Write-Host "[+] Application packaged into $tarArchive" -ForegroundColor Green

# 3. Push to Device
Write-Host "[2/4] Pushing application archive to phone storage..." -ForegroundColor Yellow
& $AdbExe push "$tarArchive" "/sdcard/ps5_controller_app.tar.gz"

# 4. Stop any old app & Install to /opt/app
Write-Host "[3/4] Installing application into /opt/app slot..." -ForegroundColor Yellow
& $AdbExe shell "chroot /data/alpine /bin/sh -c 'rm -rf /opt/app/*; tar -xzf /sdcard/ps5_controller_app.tar.gz -C /opt/app; chmod +x /opt/app/entrypoint.sh'"

# 5. Launch Kiosk App
Write-Host "[4/4] Starting PS5 Controller Kiosk App on phone screen..." -ForegroundColor Yellow
& $AdbExe shell "stop recovery 2>/dev/null; true"

if ($Foreground) {
    Write-Host "[*] Running in foreground console (Ctrl+C to stop)..." -ForegroundColor Cyan
    & $AdbExe shell "chroot /data/alpine /bin/sh /opt/app/entrypoint.sh"
} else {
    & $AdbExe shell "chroot /data/alpine /bin/sh -c 'killall python3 2>/dev/null; nohup /bin/sh /usr/local/bin/kiosk_autostart.sh > /var/log/kiosk_supervisor.log 2>&1 &'"
    Write-Host ""
    Write-Host "==================================================================" -ForegroundColor Green
    Write-Host " PS5 Controller Kiosk is now ACTIVE on the Xperia Z Ultra screen! " -ForegroundColor Green
    Write-Host " - Hold phone horizontally (Landscape) like a handheld controller" -ForegroundColor Green
    Write-Host " - Use Volume Up / Down buttons to adjust screen brightness       " -ForegroundColor Green
    Write-Host " - Touch Analog Sticks & Action Buttons for real-time control     " -ForegroundColor Green
    Write-Host "==================================================================" -ForegroundColor Green
}
