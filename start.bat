@echo off
REM PDX Save Analyzer — Double-click launcher
REM Runs start.ps1 with execution policy bypass (current process only)
powershell -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
pause
