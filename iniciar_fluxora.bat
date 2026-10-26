@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Execute instalar.bat antes de iniciar.
    pause
    exit /b 1
)
start "Fluxora" ".venv\Scripts\pythonw.exe" "%~dp0main.py"
