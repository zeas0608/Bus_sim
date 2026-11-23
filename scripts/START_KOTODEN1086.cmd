@echo off
setlocal
cd /d "%~dp0.."
echo Kotoden 1086: automated backup, UE 5.5.4 build, and editor import.
echo Save your work and CLOSE Unreal Editor before starting.
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_kotoden1086.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" (
  echo Setup stopped with an error. See the log directory: Saved\Setup1086
) else (
  echo Unreal Editor has been launched. See Saved\Setup1086\LatestImportResult.txt for import status.
)
echo.
pause
exit /b %RESULT%
