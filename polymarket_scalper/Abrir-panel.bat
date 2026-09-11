@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
title Panel del bot - Polymarket

if not exist ".venv\Scripts\scalper.exe" (
  echo.
  echo Falta instalar el bot. Abre PowerShell en esta carpeta y ejecuta:
  echo   powershell -ExecutionPolicy Bypass -File deploy\instalar-windows.ps1
  echo.
  pause
  exit /b 1
)

if not exist "logs" mkdir logs
rem abre el navegador unos segundos despues, cuando el servidor ya responde
start "" /min cmd /c "timeout /t 3 /nobreak >nul && start "" http://127.0.0.1:8787"
echo.
echo  Panel en http://127.0.0.1:8787
echo  Deja esta ventana abierta. Ctrl+C lo cierra.
echo.
.venv\Scripts\scalper.exe -c config.yaml --log-file logs\panel.log dashboard
echo.
echo  El panel se detuvo.
pause
