@echo off
rem =====================================================
rem  Deja la PWA (Libreta movil) corriendo SOLA en esta PC.
rem  Uso: scripts\instalar_servidor_pwa.bat
rem  Crea dos tareas de Windows: una la levanta al iniciar
rem  sesion y otra revisa cada 5 min que siga viva.
rem  Los celulares entran a http://192.168.0.10:8000/app
rem  (los nombres de tarea no llevan ":").
rem =====================================================
setlocal
cd /d "%~dp0.."

echo === Levantando el servidor PWA ahora ===
call "%~dp0servidor_pwa_vigia.bat" --reiniciar
if errorlevel 1 goto :error

echo.
echo === Tareas de Windows ===
schtasks /Create /F /TN "POS PWA servidor" /SC ONLOGON /TR "\"%~dp0servidor_pwa_vigia.bat\"" >nul
if not errorlevel 1 echo   "POS PWA servidor" creada (arranca al iniciar sesion, sin ventana).
schtasks /Create /F /TN "POS PWA vigia" /SC MINUTE /MO 5 /TR "\"%~dp0servidor_pwa_vigia.bat\"" >nul
if not errorlevel 1 echo   "POS PWA vigia" creada (cada 5 min revisa que siga viva).

echo.
echo ============================================
echo  LISTO. En el celular abre:
echo    http://192.168.0.10:8000/app
echo  Ya no hace falta dejar ninguna ventana abierta.
echo ============================================
pause
exit /b 0

:error
echo.
echo *** ALGO FALLO - toma foto de este error y mandala ***
pause
exit /b 1
