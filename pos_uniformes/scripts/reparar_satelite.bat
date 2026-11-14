@echo off
rem =====================================================
rem  Repara el satelite de ESTE kiosko cuando no abre
rem  ("Could not load PyInstaller's embedded PKG archive",
rem  una copia a medias o el lanzador danado por un apagon).
rem  Cierra la app, trae un lanzador BUENO (de la PC
rem  principal; si no se alcanza, del respaldo local),
rem  borra la marca de version y abre el lanzador, que
rem  copia todo completo otra vez.
rem  La ULTIMA linea es su marca de fin: el lanzador no
rem  instala un reparador cortado. No borrarla.
rem =====================================================
setlocal

rem Carpeta del lanzador de este kiosko (nunca la carpeta de red).
set "DESTINO=%~dp0"
if exist "C:\PresupuestosSatelite\" set "DESTINO=C:\PresupuestosSatelite\"
if "%DESTINO:~0,2%"=="\\" set "DESTINO=C:\PresupuestosSatelite\"
if not exist "%DESTINO%" mkdir "%DESTINO%"

rem El servidor se lee del .env de la app, igual que el lanzador (tokens=1,2:
rem sin los espacios que pueda traer al final, como el .Trim() del .ps1).
set "SERVIDOR=192.168.0.10"
set "ENVAPP=%LOCALAPPDATA%\PresupuestosSatelite\app\pos_uniformes.env"
if exist "%ENVAPP%" for /f "usebackq eol=# tokens=1,2 delims== " %%a in ("%ENVAPP%") do if /i "%%a"=="POS_UNIFORMES_SERVER_HOST" set "SERVIDOR=%%b"

echo Cerrando el satelite si esta abierto...
taskkill /F /IM "PresupuestosSatelite*" >nul 2>&1
timeout /t 3 /nobreak >nul

echo Trayendo un lanzador bueno a %DESTINO% ...
call :traer lanzador_satelite.ps1 "# Lanzador del satelite" "# Fin del lanzador del satelite"
if errorlevel 1 goto :sin_lanzador
call :traer lanzador_satelite.bat "@echo off" "rem Fin del lanzador del satelite"
if errorlevel 1 goto :sin_lanzador

echo Borrando la marca de version (para copiar todo de nuevo)...
del /q "%LOCALAPPDATA%\PresupuestosSatelite\app\VERSION.txt" >nul 2>&1

echo Abriendo el lanzador (copia la version completa)...
start "" "%DESTINO%lanzador_satelite.bat" & exit /b 0

:sin_lanzador
echo.
echo *** No hay un lanzador bueno: ni en la PC principal ni en el respaldo. ***
echo Prende la PC principal (o revisa la red) y vuelve a correr este reparador.
pause
exit /b 1

:traer
rem %1 archivo, %2 marca de inicio, %3 marca de fin.
rem Orden: la PC principal (trae siempre el mas nuevo), el respaldo local
rem y, si nada sirve, el que ya estaba si al menos empieza bien.
set "ARCH=%DESTINO%%~1"
call :copiar_validado "C:\pos_updates\%~1" "%ARCH%" "%~2" "%~3" && (echo   %~1: traido de la PC principal & exit /b 0)
call :copiar_validado "\\%SERVIDOR%\pos_updates\%~1" "%ARCH%" "%~2" "%~3" && (echo   %~1: traido de la PC principal por red & exit /b 0)
call :copiar_validado "%ARCH%.respaldo" "%ARCH%" "%~2" "%~3" && (echo   %~1: restaurado del respaldo local & exit /b 0)
call :es_bueno "%ARCH%" "%~2" "" && (echo   %~1: se queda el que ya estaba & exit /b 0)
echo   %~1: NO hay copia buena
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
rem Fin del reparador del satelite
