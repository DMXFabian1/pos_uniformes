@echo off
rem =====================================================
rem  Fuerza la actualizacion del SATELITE en esta PC:
rem  cierra el proceso (aunque este atorado), espera a
rem  que suelte los archivos y abre el lanzador, que
rem  copia la version nueva y arranca la app.
rem =====================================================
setlocal

echo Cerrando el satelite si esta abierto...
taskkill /F /IM "PresupuestosSatelite*" >nul 2>&1
timeout /t 3 /nobreak >nul

if not exist C:\PresupuestosSatelite\lanzador_satelite.bat (
    echo No esta instalado el lanzador en C:\PresupuestosSatelite.
    echo Corre primero: scripts\instalar_kiosko_aqui.bat
    pause
    exit /b 1
)

echo Abriendo el lanzador (copia la version nueva)...
start "" C:\PresupuestosSatelite\lanzador_satelite.bat
exit /b 0
