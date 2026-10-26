@echo off
rem Run the web app for the tunnel (v6 WP3). Reads optional local env overrides
rem from scripts\windows\web_env.bat (git-ignored: APP_SETUP_TOKEN,
rem APP_BACKUP_COPY_DIR, GEMINI_API_KEY, ...). Scheduled tasks do not inherit
rem interactive env vars, so everything durable lives in that file.
setlocal
set "PROJECT_DIR=%~dp0..\.."
pushd "%PROJECT_DIR%"

rem Codex R1-23: mapped drives may be invisible to elevated/service contexts.
if not exist "%PROJECT_DIR%\app\main.py" (
    echo [run_web] Khong tim thay thu muc du an: %PROJECT_DIR%
    popd & exit /b 1
)
if not exist "%PROJECT_DIR%\.venv\Scripts\python.exe" (
    echo [run_web] Chua co .venv - chay: py -3.12 -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    popd & exit /b 1
)

if exist "%~dp0web_env.bat" call "%~dp0web_env.bat"

set "APP_TRUST_PROXY=1"
set "APP_COOKIE_SECURE=1"
set "APP_DATA_DIR=%PROJECT_DIR%\data"
if not exist "%PROJECT_DIR%\data\logs" mkdir "%PROJECT_DIR%\data\logs"

rem Codex R1-23: bind 127.0.0.1 (not localhost - IPv6 risk); tunnel origin must
rem point at http://127.0.0.1:8090.
"%PROJECT_DIR%\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8090 >> "%PROJECT_DIR%\data\logs\web.log" 2>&1
popd
endlocal
