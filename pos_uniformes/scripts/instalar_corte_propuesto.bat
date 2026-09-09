@echo off
rem =====================================================
rem  Corte con permiso: a la hora del corte ya no se
rem  imprime solo — te llega la propuesta al Telegram y
rem  tu contestas /corte (o /nocorte). Si no contestas,
rem  te lo recuerda una vez 20 minutos despues.
rem  Uso: scripts\instalar_corte_propuesto.bat
rem =====================================================
setlocal
cd /d "%~dp0.."

echo === Tareas del corte (sin ventana) ===
schtasks /Create /F /TN "POS Corte 1630" /SC DAILY /ST 16:30 /TR "wscript.exe \"%~dp0correr_oculto.vbs\" corte_automatico.bat" >nul
if not errorlevel 1 echo   POS Corte 1630 - propone a las 16:30
schtasks /Create /F /TN "POS Corte 1730" /SC DAILY /ST 17:30 /TR "wscript.exe \"%~dp0correr_oculto.vbs\" corte_automatico.bat" >nul
if not errorlevel 1 echo   POS Corte 1730 - propone a las 17:30
schtasks /Create /F /TN "POS Corte recordatorio 1650" /SC DAILY /ST 16:50 /TR "wscript.exe \"%~dp0correr_oculto.vbs\" corte_automatico.bat --recordar" >nul
if not errorlevel 1 echo   POS Corte recordatorio 1650 - recuerda a las 16:50
schtasks /Create /F /TN "POS Corte recordatorio 1750" /SC DAILY /ST 17:50 /TR "wscript.exe \"%~dp0correr_oculto.vbs\" corte_automatico.bat --recordar" >nul
if not errorlevel 1 echo   POS Corte recordatorio 1750 - recuerda a las 17:50

echo.
echo === Prueba (no guarda ni imprime nada) ===
call "%~dp0corte_automatico.bat" --simular --forzar

echo.
echo ============================================
echo  LISTO. A la hora del corte te llega el
echo  mensaje al celular y tu decides:
echo    /corte    lo hace e imprime el ticket
echo    /nocorte  lo deja pasar
echo ============================================
pause
exit /b 0
