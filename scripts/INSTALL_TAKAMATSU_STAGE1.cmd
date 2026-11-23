@echo off
setlocal
cd /d "%~dp0.."
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_takamatsu_stage1.ps1"
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" (
  echo.
  echo Stage 1 installation failed. Collecting one troubleshooting report...
  powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0collect_takamatsu_stage1.ps1"
  echo.
  echo Please send Saved\TakamatsuStage1\Stage1-Diagnostics.txt to ChatGPT.
  pause
) else (
  echo.
  echo Stage 1 editor launch requested. In UE5 open L_TakamatsuStation47 and press Play.
  echo Report errors with scripts\CHECK_TAKAMATSU_STAGE1.cmd.
)
exit /b %RESULT%
