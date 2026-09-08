@echo off
rem =====================================================
rem  Configura el bot de Telegram en ESTA PC (servidor), de un jalon:
rem   1) guarda el token  2) descubre y guarda tu chat id
rem   3) manda un resumen de prueba  4) deja bot + tareas programadas
rem  Uso: scripts\configurar_telegram.bat
rem =====================================================
setlocal
cd /d "%~dp0..\.."
set "PY=%~dp0..\.venv\Scripts\python.exe"

echo === 1/4 Token del bot ===
set "TOKEN="
set /p TOKEN=Pega el token que te dio @BotFather y Enter: 
if "%TOKEN%"=="" (
    echo No escribiste nada.
    goto :error
)
"%PY%" -m pos_uniformes.scripts.resumen_diario_telegram --guardar-token "%TOKEN%"
if errorlevel 1 goto :error

echo.
echo === 2/4 Tu chat ===
echo Desde tu celular, abre el chat con el bot y mandale "hola".
pause
:chat
"%PY%" -m pos_uniformes.scripts.resumen_diario_telegram --chat-ids --guardar-chat
if errorlevel 1 (
    echo.
    echo Todavia no llega tu mensaje. Mandale "hola" al bot y presiona una tecla para reintentar.
    pause
    goto :chat
)

echo.
echo === 3/4 Resumen de prueba ===
"%PY%" -m pos_uniformes.scripts.resumen_diario_telegram
if errorlevel 1 goto :error
echo Revisa tu Telegram: debe haber llegado el resumen de hoy.

echo.
echo === 4/4 Bot escuchando + tareas programadas ===
call "%~dp0instalar_resumen_diario.bat"
if errorlevel 1 goto :error

echo.
echo ============================================
echo  LISTO. Prueba desde el celular: /estado
echo  Comandos: /corte /estado /resumen /pendientes /ayuda
echo ============================================
pause
exit /b 0

:error
echo.
echo *** ALGO FALLO - toma foto de este error y mandala ***
pause
exit /b 1
