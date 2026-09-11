@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
title Informes - Scalper Polymarket
set S=.venv\Scripts\scalper.exe

if not exist "%S%" (
  echo  Falta instalar. Ejecuta deploy\instalar-windows.ps1
  pause
  exit /b 1
)

%S% -c config.yaml overview

echo.
pause
