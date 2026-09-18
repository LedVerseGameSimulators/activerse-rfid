@echo off
setlocal EnableExtensions
title Activerse RFID Shutdown
cd /d "%~dp0"

set "QUIET=%~1"
if /i not "%QUIET%"=="/quiet" (
  echo.
  echo ==========================================
  echo        ACTIVERSE RFID - STOP SERVER
  echo ==========================================
  echo.
)

taskkill /FI "WINDOWTITLE eq Activerse RFID API*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Activerse RFID UI*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Activerse Kiosk Exit*" /T /F >nul 2>&1

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\kiosk\kill-kiosk-browser.ps1" -ProfileSlug rfid

powershell -NoProfile -Command ^
  "foreach ($p in 9000,5180) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }" >nul 2>&1

if /i "%QUIET%"=="/quiet" (
  endlocal
  exit /b 0
)

echo.
echo RFID server has stopped. Ports 9000 / 5180 are free.
echo You can close this window.
echo.
pause
endlocal
exit /b 0
