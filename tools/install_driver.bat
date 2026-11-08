@echo off
echo Installing Android WinUSB Driver for Sony Fastboot (VID_0FCE PID_0DDE)...
pnputil /add-driver "c:\Users\Bahma\Documents\GitHub\xperia-z-ultra\tools\usb_driver\android_winusb.inf" /install
echo.
echo Result code: %ERRORLEVEL%
pause
