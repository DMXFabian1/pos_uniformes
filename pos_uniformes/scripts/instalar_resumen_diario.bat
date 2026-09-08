@echo off
rem =====================================================
rem  Deja programado el resumen diario por Telegram en ESTA PC
rem  (servidor): todos los dias a la hora indicada.
rem  Uso: scripts\instalar_resumen_diario.bat [HH:MM]   (default 20:30)
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
echo   Para mandarlo ahora mismo: scripts\resumen_diario_telegram.bat
exit /b 0

:error
echo.
echo *** ALGO FALLO - revisa POS_UNIFORMES_TELEGRAM_* en pos_uniformes.env ***
pause
exit /b 1
