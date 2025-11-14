@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Use specific Python interpreter to avoid duplicate processes
REM This ensures only one Python process is created
REM Silent version - no console window
set PYTHON_PATH=C:\Users\pappahappa\AppData\Local\Programs\Python\Python313\python.exe

REM Check if Python interpreter exists
if not exist "%PYTHON_PATH%" (
    REM Fallback to default python (will show console)
    python main.py
) else (
    REM Start bot without console window
    start "" "%PYTHON_PATH%" main.py
)



