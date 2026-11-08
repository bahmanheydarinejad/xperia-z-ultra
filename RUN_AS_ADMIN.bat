@echo off
title Sony Xperia Z Ultra - Fastboot Driver Helper
echo =====================================================================
echo  Sony Xperia Z Ultra (togari) - S1Boot Fastboot Driver Setup
echo =====================================================================
echo.
echo Launching Zadig to bind WinUSB driver to S1Boot Fastboot...
echo.
start "" "%~dp0tools\zadig.exe"
echo Zadig has been launched!
echo.
echo Please follow these 3 quick steps in the Zadig window:
echo   1. Click "Options" in the top menu and select "List All Devices"
echo   2. Select "S1Boot Fastboot" from the dropdown list
echo   3. Click the big "Replace Driver" (or "Install Driver") button
echo.
echo Once completed, return to the chat and say "done"!
echo =====================================================================
pause
