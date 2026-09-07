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

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports=9000,5180; Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort } | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }" >nul 2>&1
taskkill /FI "WINDOWTITLE eq Activerse RFID API*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Activerse RFID UI*" /T /F >nul 2>&1

if /i "%QUIET%"=="/quiet" (
  endlocal
  exit /b 0
)

echo.
echo RFID server has stopped.
timeout /t 2 /nobreak >nul
exit /b 0
