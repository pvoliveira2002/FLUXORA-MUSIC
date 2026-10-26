@echo off
chcp 65001 >nul
title Fluxora 3.0 - Instalacao
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente Python...
    py -3.14 -m venv .venv 2>nul
    if errorlevel 1 py -3 -m venv .venv
    if errorlevel 1 (
        echo Nao foi possivel criar o ambiente virtual. Instale Python 3.14.
        pause
        exit /b 1
    )
)
echo Instalando bibliotecas...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Falha ao instalar. Confira a internet e sua versao do Python.
    pause
    exit /b 1
)
echo Instalacao concluida! Execute iniciar_fluxora.bat.
pause
