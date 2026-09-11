@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
title Validacion - Scalper Polymarket
set S=.venv\Scripts\scalper.exe

if not exist "%S%" (
  echo  Falta instalar. Ejecuta deploy\instalar-windows.ps1
  pause
  exit /b 1
)

echo.
echo  Estado de la medicion: cuanto se llena, cuanta ventaja hace falta,
echo  que pasa despues de cada llenado y que se esta rechazando.
echo.
%S% -c config.yaml validacion

echo.
echo  ------------------------------------------------------------------
echo  Versiones del motor que han operado:
echo.
%S% -c config.yaml experimentos

echo.
pause
