@echo off
title Sony Xperia Z Ultra — Alpine Linux SBC Console
echo =========================================================================
echo  Sony Xperia Z Ultra (togari) — Alpine Linux 3.20 SBC Console
echo =========================================================================
echo.
echo [*] Forwarding SSH port 2222 over USB ADB wire...
tools\platform-tools\adb.exe forward tcp:2222 tcp:2222
echo.
echo [*] Connecting to Alpine Linux root shell...
echo.
ssh -i "%USERPROFILE%\.ssh\id_rsa" -o StrictHostKeyChecking=no -p 2222 root@127.0.0.1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] SSH exited with code %ERRORLEVEL%.
    pause
)
