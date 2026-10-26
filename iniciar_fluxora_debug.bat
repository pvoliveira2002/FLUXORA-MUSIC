@echo off
chcp 65001 >nul
title Fluxora 3.0 - Diagnostico
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Execute instalar.bat antes de iniciar.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
    echo.
    echo O Fluxora encontrou um erro. Copie esta mensagem para o VS Code.
    pause
)
