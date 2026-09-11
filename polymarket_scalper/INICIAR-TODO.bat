@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Scalper Polymarket - arranque completo

if not exist ".venv\Scripts\scalper.exe" (
  echo.
  echo  Falta instalar el bot. Abre PowerShell en esta carpeta y ejecuta:
  echo    powershell -ExecutionPolicy Bypass -File deploy\instalar-windows.ps1
  echo.
  pause
  exit /b 1
)
if not exist "logs" mkdir logs

echo.
echo  1/3  Arrancando el bot (recolecta, simula y aprende)...
start "Bot - Scalper Polymarket" cmd /k "chcp 65001 >nul & set PYTHONUTF8=1 & set PYTHONUNBUFFERED=1 & .venv\Scripts\scalper.exe -c config.yaml --log-file logs\bot.log paper"

timeout /t 3 /nobreak >nul
echo  2/3  Arrancando el panel...
start "Panel - Scalper Polymarket" cmd /k "chcp 65001 >nul & set PYTHONUTF8=1 & .venv\Scripts\scalper.exe -c config.yaml --log-file logs\panel.log dashboard"

timeout /t 5 /nobreak >nul
echo  3/3  Abriendo el panel en el navegador...
start "" http://127.0.0.1:8787

echo.
echo  Listo. Quedaron dos ventanas abiertas:
echo    "Bot"   recolecta y simula. Dejala abierta.
echo    "Panel" sirve http://127.0.0.1:8787
echo.
echo  Para detener todo: pulsa Ctrl+C en cada ventana (guarda los datos) y cierrala.
echo.
timeout /t 8 /nobreak >nul
