@echo off
rem Register the two scheduled jobs (v6 WP3). Idempotent: existing jobs are
rem deleted first. Run from an ordinary (non-admin) PowerShell - the tasks run
rem at logon as the current user, so pre-logon availability is out of scope.
setlocal
set "PROJECT_DIR=%~dp0..\.."
set "RUN_WEB=%~dp0run_web.bat"
set "PY=%PROJECT_DIR%\.venv\Scripts\python.exe"

schtasks /Delete /TN GiaoAnWeb    /F >nul 2>&1
schtasks /Delete /TN GiaoAnBackup /F >nul 2>&1

rem Web: 1 minute after logon (let drives/mounts settle).
schtasks /Create /TN GiaoAnWeb /TR "\"%RUN_WEB%\"" /SC ONLOGON /DELAY 0001:00 /F
if errorlevel 1 (echo [install] Tao GiaoAnWeb THAT BAI & popd & exit /b 1)

rem Backup: daily 23:00.
schtasks /Create /TN GiaoAnBackup /TR "\"%PY%\" -m app.backup" /SC DAILY /ST 23:00 /F
if errorlevel 1 (echo [install] Tao GiaoAnBackup THAT BAI & exit /b 1)

echo [install] Da tao 2 task: GiaoAnWeb (logon + 1 phut), GiaoAnBackup (23:00 hang ngay).
echo [install] Neu can bien moi truong rieng, sua scripts\windows\web_env.bat
exit /b 0
