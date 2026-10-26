@echo off
schtasks /Delete /TN GiaoAnWeb    /F 2>nul
schtasks /Delete /TN GiaoAnBackup /F 2>nul
echo [uninstall] Da xoa (neu ton tai) 2 task GiaoAnWeb va GiaoAnBackup.
exit /b 0
