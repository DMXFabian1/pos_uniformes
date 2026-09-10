@echo off
rem =====================================================
rem  Deja UN supervisor oculto cuidando el bot de Telegram y
rem  la PWA (en vez de 4 tareas cada 5 min que abrian consola).
rem  Uso: scripts\instalar_supervisor.bat [sinpausa]
rem =====================================================
setlocal
cd /d "%~dp0.."

echo === Quitando las tareas viejas (vigias cada 5 min) ===
for %%T in ("POS Telegram bot" "POS Telegram vigia" "POS PWA servidor" "POS PWA vigia") do (
    schtasks /Delete /F /TN %%T >nul 2>&1
)

echo === Tareas nuevas (ocultas, via correr_oculto.vbs) ===
schtasks /Create /F /TN "POS Supervisor" /SC ONLOGON /TR "wscript.exe \"%~dp0correr_oculto.vbs\" supervisor.bat" >nul
if errorlevel 1 goto :error
echo   "POS Supervisor" al iniciar sesion.
schtasks /Create /F /TN "POS Supervisor check" /SC MINUTE /MO 30 /TR "wscript.exe \"%~dp0correr_oculto.vbs\" supervisor.bat" >nul
if errorlevel 1 goto :error
echo   "POS Supervisor check" cada 30 min (si ya corre, no hace nada).

echo === Arrancando el supervisor ahora (reinicia bot y PWA) ===
start "" /min wscript.exe "%~dp0correr_oculto.vbs" supervisor.bat --reiniciar
echo   Log: logs\supervisor.log
if /I not "%~1"=="sinpausa" pause
exit /b 0

:error
echo *** No se pudieron crear las tareas. Toma foto y mandala. ***
if /I not "%~1"=="sinpausa" pause
exit /b 1
