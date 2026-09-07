@echo off
REM One-time tech setup for Activerse RFID on a Windows PC.
setlocal EnableExtensions
cd /d "%~dp0"
title Activerse RFID - First-time setup

echo.
echo ==========================================
echo   RFID - FIRST TIME SETUP (tech only)
echo ==========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Install Python 3.11 and tick Add to PATH.
  goto :fail
)
where npm >nul 2>&1
if errorlevel 1 (
  echo ERROR: Install Node.js LTS from https://nodejs.org
  goto :fail
)

if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo Created .env from .env.example — EDIT the game IPs and ADMIN_PASSWORD.
)

if not exist "data" mkdir "data"

echo Installing Python packages...
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo Installing frontend packages...
pushd frontend
call npm install
if errorlevel 1 (
  popd
  goto :fail
)
popd

echo.
echo SETUP COMPLETE.
echo 1. Edit .env with real LAN IPs for the five games.
echo 2. Double-click START_SERVER.bat to run.
echo.
pause
exit /b 0

:fail
echo SETUP FAILED.
pause
exit /b 1
