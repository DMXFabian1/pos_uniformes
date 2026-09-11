@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
title Bot de scalping - Polymarket (paper trading)

if not exist ".venv\Scripts\scalper.exe" (
  echo.
  echo Falta instalar el bot. Abre PowerShell en esta carpeta y ejecuta:
  echo   powershell -ExecutionPolicy Bypass -File deploy\instalar-windows.ps1
  echo.
  pause
  exit /b 1
)

if not exist "logs" mkdir logs
echo.
echo  Bot en marcha. Log: logs\bot.log
echo  Deja esta ventana abierta. Ctrl+C lo detiene guardando los datos.
echo.
.venv\Scripts\scalper.exe -c config.yaml --log-file logs\bot.log paper
echo.
echo  El bot se detuvo.
pause
