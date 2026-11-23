@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_takamatsu_stage1.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo See Saved\TakamatsuStage1\Runs for details.
pause
exit /b %RESULT%
