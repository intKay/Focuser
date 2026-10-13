@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_windows.ps1" %*
if errorlevel 1 (
  echo Configuration failed. Please check the error above.
  pause
  exit /b 1
)
echo Configuration complete.
pause
