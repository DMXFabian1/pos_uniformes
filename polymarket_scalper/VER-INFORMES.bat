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

echo.
echo ============================================================
echo  QUE DATOS HAY GUARDADOS
echo ============================================================
%S% -c config.yaml status

echo.
echo ============================================================
echo  ARRASTRE ENTRE VENTANAS: ¿ir a favor o en contra de la racha?
echo ============================================================
%S% -c config.yaml updown-study

echo.
echo ============================================================
echo  RESULTADOS POR TIPO DE SENAL (predicho contra real)
echo ============================================================
%S% -c config.yaml report

echo.
echo ============================================================
echo  MODELOS APRENDIDOS
echo ============================================================
%S% -c config.yaml models

echo.
echo ============================================================
echo  USO DE DISCO
echo ============================================================
%S% -c config.yaml retention

echo.
pause
