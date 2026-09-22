@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python -m nexo7 serve --open
) else (
  py -3 -m nexo7 serve --open
)
if errorlevel 1 pause
