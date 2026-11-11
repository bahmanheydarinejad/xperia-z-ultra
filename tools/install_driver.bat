@echo off
title Android Universal WinUSB / ADB Driver Installer
echo =========================================================================
echo  Universal Android ADB / WinUSB Driver Installer
echo =========================================================================
echo.
echo [*] Installing Android WinUSB Driver into Windows Driver Store...
pnputil /add-driver "%~dp0usb_driver\android_winusb.inf" /install
echo.
echo Result code: %ERRORLEVEL%
if %ERRORLEVEL% EQU 0 (
    echo [+] Driver installation successful!
) else (
    echo [!] Note: Installing drivers requires Administrator privileges.
    echo     If it failed, right-click and 'Run as administrator'.
)
echo.
pause
