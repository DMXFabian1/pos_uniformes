@echo off
rem =====================================================
rem  Deja programado el resumen diario por Telegram en ESTA PC
rem  (servidor): todos los dias a la hora indicada.
rem  Uso: scripts\instalar_resumen_diario.bat [HH:MM] [auto]   (default 20:30; "auto" activa el corte por hora)
rem =====================================================
setlocal
set "HORA=%~1"
if "%HORA%"=="" set "HORA=20:30"
cd /d "%~dp0.."

echo === Probando el resumen (sin enviar) ===
call "%~dp0resumen_diario_telegram.bat" --imprimir
if errorlevel 1 goto :error

echo.
echo === Tarea de Windows "POS Resumen diario" a las %HORA% ===
schtasks /Create /F /TN "POS Resumen diario" /SC DAILY /ST %HORA% /TR "\"%~dp0resumen_diario_telegram.bat\"" >nul
if errorlevel 1 goto :error
echo   Listo. Cada dia a las %HORA% llega el resumen a tu Telegram.
schtasks /Create /F /TN "POS Pendientes" /SC DAILY /ST 13:30 /TR "\"%~dp0resumen_diario_telegram.bat\" --pendientes" >nul
if not errorlevel 1 echo   Y a las 13:30 un recordatorio con lo que falta por registrar (pagos, faltas).
echo.
echo === Bot de Telegram (/corte, /estado, /resumen, /pendientes) ===
schtasks /Create /F /TN "POS Telegram bot" /SC ONLOGON /TR "\"%~dp0telegram_bot.bat\"" >nul
if not errorlevel 1 echo   Tarea "POS Telegram bot" creada (arranca al iniciar sesion).
start "POS Telegram bot" "%~dp0telegram_bot.bat"
if /I "%~2"=="auto" (
    echo.
    echo === Corte automatico 30 min antes de cerrar (17:30; jueves y domingo 16:30) ===
    schtasks /Create /F /TN "POS Corte 16:30" /SC DAILY /ST 16:30 /TR "\"%~dp0corte_automatico.bat\"" >nul
    schtasks /Create /F /TN "POS Corte 17:30" /SC DAILY /ST 17:30 /TR "\"%~dp0corte_automatico.bat\"" >nul
    echo   Tareas de corte automatico creadas.
) else (
    echo   Corte automatico por hora NO activado: Daniel lo ordena con /corte. ^(instalar_resumen_diario.bat HH:MM auto lo activa^)
)
echo   Para mandarlo ahora mismo: scripts\resumen_diario_telegram.bat
exit /b 0

:error
echo.
echo *** ALGO FALLO - revisa POS_UNIFORMES_TELEGRAM_* en pos_uniformes.env ***
pause
exit /b 1
