@echo off
rem Lanzador del satelite (acceso directo del kiosko); la logica vive en el .ps1.
rem Antes de abrir el .ps1 revisa que este completo y, si no, lo restaura.
rem (byte 216: ver nota abajo)
goto :inicio
exit /b
:inicio
rem NOTA: cmd.exe lee el .bat linea por linea mientras corre. El lanzador.bat
rem viejo media 216 bytes y el .ps1 viejo lo reemplazaba mientras cmd esperaba;
rem al volver, cmd sigue leyendo en el byte 216 de ESTE archivo, donde esta
rem el "exit /b" de arriba. No mover las primeras lineas.
setlocal
set "PS1=%~dp0lanzador_satelite.ps1"

call :ps1_bueno "%PS1%" && goto :abrir
echo El lanzador de este kiosko esta danado; buscando una copia buena...
call :restaurar "%PS1%.respaldo" && goto :abrir
set "SERVIDOR=192.168.0.10"
set "ENVAPP=%LOCALAPPDATA%\PresupuestosSatelite\app\pos_uniformes.env"
if exist "%ENVAPP%" for /f "usebackq eol=# tokens=1,* delims== " %%a in ("%ENVAPP%") do if /i "%%a"=="POS_UNIFORMES_SERVER_HOST" set "SERVIDOR=%%b"
if exist "C:\pos_updates\lanzador_satelite.ps1" call :restaurar "C:\pos_updates\lanzador_satelite.ps1" && goto :abrir
call :restaurar "\\%SERVIDOR%\pos_updates\lanzador_satelite.ps1" && goto :abrir
rem Sin copia buena: si al menos empieza bien, se intenta abrir igual.
findstr /b /l /c:"# Lanzador del satelite" "%PS1%" >nul 2>&1 && goto :abrir
echo.
echo *** El lanzador de este kiosko esta danado y no hay copia buena. ***
echo Prende la PC principal (o revisa la red), vuelve a abrir este acceso
echo o corre reparar_satelite.bat.
pause
exit /b 1

:abrir
rem Todo en UNA linea: el .ps1 puede reemplazar este .bat mientras corre.
powershell -ExecutionPolicy Bypass -File "%PS1%" & exit /b

:ps1_bueno
findstr /b /l /c:"# Lanzador del satelite" "%~1" >nul 2>&1 || exit /b 1
findstr /b /l /c:"# Fin del lanzador del satelite" "%~1" >nul 2>&1 || exit /b 1
exit /b 0

:restaurar
rem Copia a .nuevo, valida y solo entonces reemplaza (move en el mismo disco).
call :ps1_bueno "%~1" || exit /b 1
copy /y "%~1" "%PS1%.nuevo" >nul 2>&1 || exit /b 1
for %%A in ("%~1") do set "T1=%%~zA"
for %%A in ("%PS1%.nuevo") do set "T2=%%~zA"
if not "%T1%"=="%T2%" (del /q "%PS1%.nuevo" >nul 2>&1 & exit /b 1)
call :ps1_bueno "%PS1%.nuevo" || (del /q "%PS1%.nuevo" >nul 2>&1 & exit /b 1)
move /y "%PS1%.nuevo" "%PS1%" >nul 2>&1 || exit /b 1
echo Lanzador restaurado desde %~1
exit /b 0
rem Fin del lanzador del satelite (bat)
