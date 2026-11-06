@echo off
rem =====================================================
rem  Actualiza el POS en la PC principal (todo en uno):
rem  git pull + migraciones + build + publicar a kioskos
rem  Uso: scripts\actualizar_pc_principal.bat
rem =====================================================
setlocal
cd /d "%~dp0.."

rem Auto-log: todo lo que salga en pantalla queda tambien en
rem reportes\ultimo_update.log (para mandarlo con enviar_reporte.bat)
if not exist reportes mkdir reportes
if not defined POS_UPDATE_LOGGING (
    set POS_UPDATE_LOGGING=1
    call "%~f0" 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath 'reportes\ultimo_update.log'"
    exit /b %ERRORLEVEL%
)

echo === Actualizacion del %date% %time% ===
echo === 1/3 Trayendo lo nuevo del repositorio ===
git pull
if errorlevel 1 goto :error

echo.
echo === 2/3 Build, respaldo, migraciones y publicacion ===
rem El orden y la vuelta atras viven en scripts\actualizar.py: primero el build
rem (sin publicar), luego respaldo + migraciones, y al final se publica a los
rem kioskos. Si algo falla antes de publicar, la base no se toca y el codigo
rem regresa a lo que corren los kioskos. Avisa por Telegram como termino.
call scripts\actualizar_seguro.bat
if errorlevel 1 goto :error

echo.
echo === 3/3 Dejando tareas y servicios al dia (y los pasos de una sola vez) ===
call scripts\postactualizacion.bat --pasos-unicos

echo.
echo ============================================
echo  LISTO. Version publicada para kioskos:
if exist C:\pos_updates\PresupuestosSatelite\VERSION.txt (
    type C:\pos_updates\PresupuestosSatelite\VERSION.txt
) else (
    echo  (no se encontro C:\pos_updates - revisa el share)
)
echo ============================================
pause
exit /b 0

:error
echo.
echo *** ALGO FALLO - arriba dice que paso y como quedo todo. ***
echo     Tambien llego por Telegram; el detalle esta en reportes\ultimo_update.log
pause
exit /b 1
