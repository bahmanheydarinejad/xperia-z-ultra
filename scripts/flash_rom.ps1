# ==============================================================================
# Sony Xperia Z Ultra (togari) - Custom ROM (LineageOS) Flasher
# ==============================================================================
param (
    [string]$RomZip = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path "$ScriptDir\..").Path
$AdbExe = "$ProjectRoot\tools\platform-tools\adb.exe"

if (-not $RomZip) {
    $RomZip = "$ProjectRoot\downloads\lineage-20.0-20231020-UNOFFICIAL-togari.zip"
}

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "      Sony Xperia Z Ultra (togari) - LineageOS ROM Installer      " -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

if (-not (Test-Path $RomZip)) {
    Write-Host "[-] Error: ROM zip package not found at: $RomZip" -ForegroundColor Red
    exit 1
}

$romItem = Get-Item $RomZip
$romLeaf = Split-Path $RomZip -Leaf
$romSizeMb = [math]::Round($romItem.Length / 1MB, 2)
Write-Host "[+] ROM Package: $romLeaf ($romSizeMb MB)" -ForegroundColor Green

# 1. Wait for Device in ADB mode (Recovery or Sideload)
Write-Host "[*] Waiting for Xperia Z Ultra in TWRP Recovery or Sideload mode..." -ForegroundColor Yellow
Write-Host "    (Please ensure phone is connected via USB cable to PC)" -ForegroundColor Gray

$detected = $false
$mode = ""
$deviceId = ""
$attempts = 0
while (-not $detected) {
    $lines = & $AdbExe devices
    foreach ($line in $lines) {
        $trimmed = $line.Trim()
        if ($trimmed -match '^([a-zA-Z0-9_\-\.]+)\s+(device|recovery|sideload)$') {
            $deviceId = $matches[1]
            $mode = $matches[2]
            $detected = $true
            break
        }
    }

    if (-not $detected) {
        $attempts++
        if ($attempts % 5 -eq 0) {
            Write-Host "    ... still waiting for device connection (elapsed: $($attempts * 2)s)" -ForegroundColor Gray
        }
        Start-Sleep -Seconds 2
    }
}

Write-Host "[+] Device detected ($deviceId) in mode: $mode" -ForegroundColor Green

# 2. Flash ROM
if ($mode -eq "sideload") {
    Write-Host "[*] Sideloading ROM to device ($deviceId)..." -ForegroundColor Yellow
    & $AdbExe -s $deviceId sideload $RomZip
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[-] Sideload failed with code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "[+] Sideload finished!" -ForegroundColor Green
} else {
    Write-Host "[1/3] Pushing ROM package to /sdcard/ on device ($deviceId)..." -ForegroundColor Yellow
    $dest = "/sdcard/$romLeaf"
    & $AdbExe -s $deviceId push $RomZip $dest
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[-] Push failed with code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }

    Write-Host "[2/3] Executing automated TWRP install command..." -ForegroundColor Yellow
    & $AdbExe -s $deviceId shell "twrp install $dest"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[-] TWRP install command returned code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }

    Write-Host "[3/3] Installation completed successfully!" -ForegroundColor Green
}

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host " LineageOS installation finished! You can now reboot to system.   " -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
