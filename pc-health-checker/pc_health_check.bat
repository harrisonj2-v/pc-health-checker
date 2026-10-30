@echo off
REM Double-click launcher for the PowerShell PC health checker.
REM Runs the check, saves the report next to this file, and keeps the
REM window open so you can read the results.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pc_health_check.ps1" -Save
echo.
pause
