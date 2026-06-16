@echo off
title HBD Dashboard Automation Control Panel

:: Define colors using ANSI escape sequences (supported in Windows 10/11)
for /f "delims=" %%a in ('powershell -Command "[char]27"') do set "ESC=%%a"
set "GREEN=%ESC%[92m"
set "CYAN=%ESC%[96m"
set "YELLOW=%ESC%[93m"
set "RED=%ESC%[91m"
set "MAGENTA=%ESC%[95m"
set "RESET=%ESC%[0m"
set "BOLD=%ESC%[1m"

cls
echo =====================================================================
echo %BOLD%%CYAN%       __  __ ____   ____     _____            _     _                 _ %RESET%
echo %BOLD%%CYAN%      ^|  ^|/  ^|  _ \ ^|  _ \   ^|  __ \          ^| ^|   ^| ^|               ^| ^|%RESET%
echo %BOLD%%CYAN%      ^| \  / ^| ^|_) ^| ^|_) ^|  ^| ^|  ^| ^| __ _ ___^| ^|__ ^| ^|__   ___   __ _^| ^|__ _%RESET%
echo %BOLD%%CYAN%      ^| ^|\/^| ^|  _ ^< ^|  _  /   ^| ^|  ^| ^|/ _` / __^| '_ \^| '_ \ / _ \ / _` ^| '__^| _^|%RESET%
echo %BOLD%%CYAN%      ^| ^|  ^| ^| ^|_) ^| ^| \ \   ^| ^|__^| ^| (_^| \__ \ ^| ^| ^| ^|_) ^| (_) ^| (_^| ^| ^|  ^| ^|_ %RESET%
echo %BOLD%%CYAN%      ^|_^|  ^|_^|____/ ^|_^|  \_\  ^|_____/ \__,_^|___/_^| ^|_^|_.__/ \___/ \__,_^|_^|   \__^|%RESET%
echo =====================================================================
echo %BOLD%%YELLOW%           HBD Dashboard Automation - One-Click Startup Script%RESET%
echo =====================================================================
echo.

:: Check if virtual environment exists
if not exist "%~dp0venv\Scripts\activate.bat" (
    echo %RED%[ERROR] Virtual environment 'venv' not found in the root directory!%RESET%
    echo %YELLOW%Please ensure your python virtual environment is installed at: %~dp0venv%RESET%
    echo.
    pause
    exit /b 1
)

:: Check if Node.js is installed (required for frontend)
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[WARNING] npm [Node.js] was not found in your PATH!%RESET%
    echo %YELLOW%The frontend service might fail to start if Node.js/npm is not installed.%RESET%
    echo.
)

echo %GREEN%[1/4] Starting Frontend Dev Server (Vite)...%RESET%
start "HBD Dashboard - Frontend Dev Server" cmd /k "cd /d "%~dp0frontend" && title HBD Dashboard - Frontend Dev Server && echo Starting Frontend Dev Server... && npm run dev"

echo %GREEN%[2/4] Starting Backend Flask API Server...%RESET%
start "HBD Dashboard - Flask API Server" cmd /k "cd /d "%~dp0backend" && title HBD Dashboard - Flask API Server && echo Activating virtual environment... && call "%~dp0venv\Scripts\activate.bat" && echo Starting Flask server... && python app.py --runserver"

echo %GREEN%[3/4] Starting Celery Worker (CSV Processor)...%RESET%
:: Using PowerShell to execute start_worker.ps1 safely with venv activated
start "HBD Dashboard - Celery Worker" powershell -NoExit -ExecutionPolicy Bypass -Command "title 'HBD Dashboard - Celery Worker'; cd '%~dp0backend'; . '..\venv\Scripts\Activate.ps1'; .\start_worker.ps1"

echo %GREEN%[4/4] Starting GDrive Scanner...%RESET%
start "HBD Dashboard - GDrive Scanner" cmd /k "cd /d "%~dp0backend" && title HBD Dashboard - GDrive Scanner && echo Activating virtual environment... && call "%~dp0venv\Scripts\activate.bat" && echo Starting GDrive Scanner... && python worker_etl.py"

echo.
echo %BOLD%%MAGENTA%=====================================================================%RESET%
echo %BOLD%%GREEN%  SUCCESS: All 4 services are starting in separate windows!%RESET%
echo %BOLD%%MAGENTA%=====================================================================%RESET%
echo   1. Frontend Dev Server  - http://localhost:5173
echo   2. Backend Flask API    - http://localhost:8001
echo   3. Celery Worker        - Processing CSV tasks in the background
echo   4. GDrive Scanner       - Monitoring Google Drive changes
echo.
echo %YELLOW%  Tip: Keep these windows open while working.%RESET%
echo %YELLOW%       To stop a service, simply close its window or press Ctrl+C in it.%RESET%
echo.
pause
