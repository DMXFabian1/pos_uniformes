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

rem Trae el lanzador nuevo del servidor (por si el arreglo vive ahi).
copy /y "\\192.168.0.10\pos_updates\lanzador_satelite.ps1" C:\PresupuestosSatelite\ >nul 2>&1
copy /y "\\192.168.0.10\pos_updates\lanzador_satelite.bat" C:\PresupuestosSatelite\ >nul 2>&1

rem Borra la marca de version: asi el lanzador copia TODO de nuevo, aunque el
rem numero coincida (sirve cuando el .exe quedo a medias y no abre).
del /q "%LOCALAPPDATA%\PresupuestosSatelite\app\VERSION.txt" >nul 2>&1

echo Abriendo el lanzador (copia la version completa de nuevo)...
start "" C:\PresupuestosSatelite\lanzador_satelite.bat
exit /b 0
