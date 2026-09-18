@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%CD%"

if not defined ACTIVERSE_KIOSK set "ACTIVERSE_KIOSK=1"

title Activerse RFID - Starting
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
start "Activerse RFID API" /MIN /D "%ROOT%" cmd /k "python -m api.main"
ping -n 3 127.0.0.1 >nul

echo Starting RFID UI (port 5180)...
set "WINDOW_TITLE_UI=Activerse RFID UI"
call "%ROOT%\scripts\kiosk\run-ui-prod.bat" 5180
if errorlevel 1 goto :failed
ping -n 3 127.0.0.1 >nul

echo Waiting for RFID UI...
set /a _tries=0

:wait_ui
set /a _tries+=1
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:5180/' -UseBasicParsing -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto ui_ready
if %_tries% GEQ 30 goto ui_timeout
ping -n 2 127.0.0.1 >nul
goto wait_ui

:ui_timeout
echo WARNING: UI did not respond yet. Opening browser anyway.
goto check_api

:ui_ready
echo RFID UI is ready.

:check_api
echo Checking API health...
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -UseBasicParsing 'http://localhost:9000/health' -TimeoutSec 3; if ($r.StatusCode -ne 200) { exit 1 } } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo WARNING: /health not confirmed yet. Check the RFID API window.
)

call "%ROOT%\scripts\kiosk\open-ui.bat" 5180 rfid

echo.
echo ========================================
echo   ACTIVERSE RFID is running
echo   Open:  http://127.0.0.1:5180/
echo   Ctrl+Shift+K exits fullscreen kiosk
echo   To stop: double-click STOP_SERVER.bat
echo ========================================
echo.
exit /b 0

:failed
echo.
echo START FAILED. See OPERATOR_GUIDE.md or ask tech.
pause
exit /b 1
