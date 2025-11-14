@echo off
chcp 65001 >nul
cd /d "%~dp0"
taskkill /F /IM python.exe >nul 2>&1
python main.py
pause
