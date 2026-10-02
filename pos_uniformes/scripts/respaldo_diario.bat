@echo off
rem =====================================================
rem  Respaldo diario de la base. Lo corre la tarea
rem  "POS Respaldo" todos los dias; tambien se puede dar
rem  doble clic para hacer uno ahora mismo.
rem  Avisa por Telegram SOLO si algo sale mal.
rem =====================================================
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.respaldo_diario %*
set CODIGO=%ERRORLEVEL%
if not "%1"=="--callado" (
    if %CODIGO% NEQ 0 (
        echo.
        echo *** El respaldo NO salio - revisa el mensaje de arriba ***
    )
    if not "%POS_RESPALDO_SIN_PAUSA%"=="1" pause
)
exit /b %CODIGO%
