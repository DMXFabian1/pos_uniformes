@echo off
rem =====================================================
rem  Deja programado el resumen diario por Telegram en ESTA PC
rem  (servidor): todos los dias a la hora indicada.
rem  Uso: scripts\instalar_resumen_diario.bat [HH:MM] [auto]
rem  Sin hora: resumen 15 min antes de cerrar (17:45; jue/dom 16:45). Con HH:MM: hora fija. "auto" activa el corte por hora.
rem  Los nombres de tarea no llevan ":" (Windows los guarda como archivos y ese caracter no vale).
rem =====================================================
setlocal
set "HORA=%~1"
cd /d "%~dp0.."

echo === Probando el resumen (sin enviar) ===
call "%~dp0resumen_diario_telegram.bat" --imprimir
if errorlevel 1 goto :error

echo.
if "%~1"=="" (
    echo === Resumen 15 min antes de cerrar: 17:45, jueves y domingo 16:45 ===
    schtasks /Create /F /TN "POS Resumen 1645" /SC DAILY /ST 16:45 /TR "wscript.exe \"%~dp0correr_oculto.vbs\" resumen_diario_telegram.bat --si-toca" >nul
    if errorlevel 1 goto :error
    schtasks /Create /F /TN "POS Resumen 1745" /SC DAILY /ST 17:45 /TR "wscript.exe \"%~dp0correr_oculto.vbs\" resumen_diario_telegram.bat --si-toca" >nul
    if errorlevel 1 goto :error
    schtasks /Delete /F /TN "POS Resumen diario" >nul 2>&1
    echo   Listo. El script decide cada dia cual de las dos toca segun el horario de la tienda.
) else (
    echo === Tarea de Windows "POS Resumen diario" a las %HORA% (hora fija) ===
    schtasks /Create /F /TN "POS Resumen diario" /SC DAILY /ST %HORA% /TR "wscript.exe \"%~dp0correr_oculto.vbs\" resumen_diario_telegram.bat" >nul
    if errorlevel 1 goto :error
    echo   Listo. Cada dia a las %HORA% llega el resumen a tu Telegram.
)
schtasks /Create /F /TN "POS Pendientes" /SC DAILY /ST 13:30 /TR "wscript.exe \"%~dp0correr_oculto.vbs\" resumen_diario_telegram.bat --pendientes" >nul
if not errorlevel 1 echo   Y a las 13:30 un recordatorio con lo que falta por registrar (pagos, faltas).
echo.
echo === Bot de Telegram (/corte, /estado, /resumen, /pendientes) ===
schtasks /Create /F /TN "POS Telegram bot" /SC ONLOGON /TR "wscript.exe \"%~dp0correr_oculto.vbs\" telegram_bot_vigia.bat" >nul
if not errorlevel 1 echo   Tarea "POS Telegram bot" creada (arranca al iniciar sesion, sin ventana).
schtasks /Create /F /TN "POS Telegram vigia" /SC MINUTE /MO 5 /TR "wscript.exe \"%~dp0correr_oculto.vbs\" telegram_bot_vigia.bat" >nul
if not errorlevel 1 echo   Tarea "POS Telegram vigia" creada (cada 5 min revisa que el bot viva, sin parpadeo).
call "%~dp0telegram_bot_vigia.bat" --reiniciar
if /I "%~2"=="auto" (
    echo.
    echo === Corte automatico 30 min antes de cerrar (17:30; jueves y domingo 16:30) ===
    schtasks /Create /F /TN "POS Corte 1630" /SC DAILY /ST 16:30 /TR "wscript.exe \"%~dp0correr_oculto.vbs\" corte_automatico.bat" >nul
    schtasks /Create /F /TN "POS Corte 1730" /SC DAILY /ST 17:30 /TR "wscript.exe \"%~dp0correr_oculto.vbs\" corte_automatico.bat" >nul
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
