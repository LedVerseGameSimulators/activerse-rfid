@echo off
setlocal EnableExtensions
title Activerse RFID Launcher
cd /d "%~dp0"
set "ROOT=%CD%"

echo.
echo ==========================================
echo       ACTIVERSE RFID - START SERVER
echo ==========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    ) else (
        echo ERROR: Python 3.11 is not installed.
        echo Ask tech to install Python 3.11, then run SETUP_FIRST_TIME.bat.
        goto :failed
    )
)

where npm >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js/npm is not installed.
    echo Ask tech to install Node.js LTS, then run SETUP_FIRST_TIME.bat.
    goto :failed
)

if not exist ".env" (
    if exist ".env.example" (
        echo Creating .env from .env.example ...
        copy /Y ".env.example" ".env" >nul
        echo.
        echo IMPORTANT: Edit .env and set the five game PC IPs + ADMIN_PASSWORD.
        echo Then run START_SERVER.bat again.
        goto :failed
    ) else (
        echo ERROR: .env is missing. Ask tech to create it from .env.example.
        goto :failed
    )
)

if not exist "data" mkdir "data"

echo Checking Python packages...
python -c "import fastapi, uvicorn, httpx, dotenv" >nul 2>&1
if errorlevel 1 (
    echo Installing required Python packages (first time)...
    python -m pip install -r "requirements.txt"
    if errorlevel 1 goto :failed
)

if not exist "frontend\node_modules" (
    echo Installing frontend packages (first time)...
    pushd "frontend"
    call npm install
    if errorlevel 1 (
        popd
        goto :failed
    )
    popd
)

echo Stopping any previous RFID copy...
call "%ROOT%\STOP_SERVER.bat" /quiet
ping -n 2 127.0.0.1 >nul

echo Starting RFID API on port 9000...
start "Activerse RFID API" /min cmd.exe /k "cd /d %ROOT% && python -m api.main"

echo Starting RFID UI on port 5180...
start "Activerse RFID UI" /min cmd.exe /k "cd /d %ROOT%\frontend && npm run dev -- --port 5180 --strictPort"

echo Waiting for services...
timeout /t 5 /nobreak >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -UseBasicParsing 'http://localhost:9000/health' -TimeoutSec 3; if ($r.StatusCode -ne 200) { exit 1 } } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo WARNING: /health not confirmed yet. Check the RFID API window.
    echo Opening UI anyway...
)

echo.
echo RFID server is ready.
echo Opening http://localhost:5180
echo.
start "" "http://localhost:5180"
timeout /t 2 /nobreak >nul
exit /b 0

:failed
echo.
echo START FAILED. See OPERATOR_GUIDE.md or ask tech.
pause
exit /b 1
