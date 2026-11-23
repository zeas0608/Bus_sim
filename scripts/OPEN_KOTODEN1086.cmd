@echo off
setlocal
cd /d "%~dp0.."
echo Open existing Kotoden bus 1086 map WITHOUT import or build.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0open_kotoden1086.ps1"
if errorlevel 1 (
 echo The bus could not be opened. Do not repeat import. Run CHECK_1086_ERROR.cmd.
 pause
)
