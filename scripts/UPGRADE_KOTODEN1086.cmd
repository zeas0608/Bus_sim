@echo off
setlocal
cd /d "%~dp0.."
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_kotoden1086.ps1" -Upgrade
set "result=%errorlevel%"
if not "%result%"=="0" (
  echo Upgrade stopped. See Saved\Setup1086 or run scripts\CHECK_1086_ERROR.cmd.
  pause
)
exit /b %result%
