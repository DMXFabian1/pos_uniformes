@echo off
rem Programa el envio del snapshot a la casa cada 15 minutos
rem (solo corre mientras esta PC este prendida). Correr UNA vez
rem como administrador en la PC principal.
schtasks /Create /F /SC MINUTE /MO 15 /TN "POS Snapshot Casa" ^
    /TR "\"%~dp0enviar_snapshot_casa.bat\"" >nul
if errorlevel 1 (
    echo No se pudo crear la tarea. Corre este .bat como administrador.
    pause
    exit /b 1
)
echo Tarea creada: cada 15 min se manda el snapshot a la casa.
pause
exit /b 0
