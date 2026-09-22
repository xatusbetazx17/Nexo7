@echo off
cd /d "%~dp0"
py -3 -m nexo7.desktop
if errorlevel 1 pause
