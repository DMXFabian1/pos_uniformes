@echo off
rem =====================================================
rem  Deja UN supervisor oculto cuidando el bot de Telegram y
rem  la PWA. Ya NO hace falta correrlo a mano: cada
rem  actualizacion lo aplica sola (postactualizacion.bat).
rem  Uso: scripts\instalar_supervisor.bat [sinpausa]
rem =====================================================
setlocal
cd /d "%~dp0.."

echo === Dejando tareas y servicios al dia ===
call "%~dp0postactualizacion.bat" --forzar

echo.
echo ============================================
echo  LISTO. Un solo supervisor oculto cuida el bot
echo  de Telegram y la PWA. Log: logs\supervisor.log
echo ============================================
if /I not "%~1"=="sinpausa" pause
exit /b 0
