@echo off
rem Actualizacion sin nadie mirando: la dispara el bot (/actualizar) o la tarea
rem de la noche. Trae lo nuevo, actualiza con cuidado y deja tareas y servicios
rem al dia. Todo queda en reportes\ultimo_update.log y el resultado llega por
rem Telegram. Si la actualizacion no quedo, NO corre la postactualizacion.
setlocal
cd /d "%~dp0.."
if not exist reportes mkdir reportes
echo === Actualizacion desatendida del %date% %time% === > reportes\ultimo_update.log
call scripts\actualizar_seguro.bat --traer >> reportes\ultimo_update.log 2>&1
if errorlevel 1 exit /b 1
call scripts\postactualizacion.bat --pasos-unicos >> reportes\ultimo_update.log 2>&1
exit /b 0
