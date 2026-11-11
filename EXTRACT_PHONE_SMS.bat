@echo off
title Universal Phone SMS Extractor & Dashboard Builder
cls
echo =========================================================================
echo   Universal Android SMS Intelligence & Dashboard Builder
echo =========================================================================
echo.
echo [*] Checking Python environment...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Python 3 is not found in PATH!
    echo     Please ensure Python 3 is installed.
    pause
    exit /b 1
)

echo [*] Launching Smart Device Detector & SMS Engine...
echo.
python tools\generate_phone_sms.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Process finished with warnings or errors (Code: %ERRORLEVEL%).
)

echo.
pause
