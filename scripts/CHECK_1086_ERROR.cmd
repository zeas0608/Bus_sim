@echo off
setlocal
cd /d "%~dp0.."
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0collect_1086_diagnostics.ps1"
if errorlevel 1 (
  echo Could not collect Unreal diagnostics.
  pause
)
