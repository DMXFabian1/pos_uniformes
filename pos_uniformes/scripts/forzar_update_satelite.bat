@echo off
rem =====================================================
rem  Fuerza la actualizacion del SATELITE en esta PC:
rem  cierra el proceso (aunque este atorado), espera a
rem  que suelte los archivos, trae el lanzador nuevo del
rem  servidor SIN pisar el bueno a ciegas y abre el
rem  lanzador, que copia la version nueva y arranca la app.
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
set "DESTINO=C:\PresupuestosSatelite\"

rem El servidor se lee del .env de la app, igual que el lanzador.
set "SERVIDOR=192.168.0.10"
set "ENVAPP=%LOCALAPPDATA%\PresupuestosSatelite\app\pos_uniformes.env"
if exist "%ENVAPP%" for /f "usebackq eol=# tokens=1,* delims== " %%a in ("%ENVAPP%") do if /i "%%a"=="POS_UNIFORMES_SERVER_HOST" set "SERVIDOR=%%b"

rem Trae el lanzador nuevo del servidor (por si el arreglo vive ahi): a .nuevo,
rem validado, y solo entonces reemplaza. Si no se puede, se queda el que hay.
echo Trayendo el lanzador nuevo...
call :traer lanzador_satelite.ps1 "# Lanzador del satelite" "# Fin del lanzador del satelite"
call :traer lanzador_satelite.bat "@echo off" "rem Fin del lanzador del satelite"

rem Borra la marca de version: asi el lanzador copia TODO de nuevo, aunque el
rem numero coincida (sirve cuando el .exe quedo a medias y no abre).
del /q "%LOCALAPPDATA%\PresupuestosSatelite\app\VERSION.txt" >nul 2>&1

echo Abriendo el lanzador (copia la version completa de nuevo)...
start "" C:\PresupuestosSatelite\lanzador_satelite.bat & exit /b 0

:traer
rem %1 archivo, %2 marca de inicio, %3 marca de fin.
set "ARCH=%DESTINO%%~1"
call :copiar_validado "C:\pos_updates\%~1" "%ARCH%" "%~2" "%~3" && (echo   %~1: traido de la PC principal & exit /b 0)
call :copiar_validado "\\%SERVIDOR%\pos_updates\%~1" "%ARCH%" "%~2" "%~3" && (echo   %~1: traido de la PC principal por red & exit /b 0)
call :es_bueno "%ARCH%" "%~2" "" && (echo   %~1: no se alcanzo el servidor, se queda el que hay & exit /b 0)
call :copiar_validado "%ARCH%.respaldo" "%ARCH%" "%~2" "%~3" && (echo   %~1: restaurado del respaldo local & exit /b 0)
echo   %~1: NO hay copia buena; corre reparar_satelite.bat
exit /b 1

:es_bueno
rem %1 archivo, %2 marca de inicio, %3 marca de fin (vacia = no se revisa).
findstr /b /l /c:"%~2" "%~1" >nul 2>&1 || exit /b 1
if not "%~3"=="" findstr /b /l /c:"%~3" "%~1" >nul 2>&1 || exit /b 1
exit /b 0

:copiar_validado
rem %1 origen, %2 destino, %3/%4 marcas. Copia a .nuevo, valida (marcas y
rem mismo tamano) y solo entonces reemplaza con move (mismo disco).
call :es_bueno "%~1" "%~3" "%~4" || exit /b 1
copy /y "%~1" "%~2.nuevo" >nul 2>&1 || exit /b 1
set "T1=" & set "T2="
for %%A in ("%~1") do set "T1=%%~zA"
for %%A in ("%~2.nuevo") do set "T2=%%~zA"
if not "%T1%"=="%T2%" (del /q "%~2.nuevo" >nul 2>&1 & exit /b 1)
call :es_bueno "%~2.nuevo" "%~3" "%~4" || (del /q "%~2.nuevo" >nul 2>&1 & exit /b 1)
move /y "%~2.nuevo" "%~2" >nul 2>&1 || exit /b 1
exit /b 0
