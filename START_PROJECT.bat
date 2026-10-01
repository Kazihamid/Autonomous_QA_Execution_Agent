@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-project.ps1"
if errorlevel 1 (
  echo.
  echo Startup failed. Read START_HERE.md or run VIEW_LOGS.bat.
  pause
)
