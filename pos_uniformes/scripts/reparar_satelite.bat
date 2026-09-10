@echo off
rem =====================================================
rem  Repara el satelite de ESTE kiosko cuando no abre
rem  ("Could not load PyInstaller's embedded PKG archive"
rem  o se quedo con una copia a medias).
rem  Cierra la app, borra la marca de version y abre el
rem  lanzador, que copia todo completo otra vez.
rem =====================================================
setlocal

echo Cerrando el satelite si esta abierto...
taskkill /F /IM "PresupuestosSatelite*" >nul 2>&1
timeout /t 3 /nobreak >nul

echo Borrando la marca de version (para copiar todo de nuevo)...
del /q "%LOCALAPPDATA%\PresupuestosSatelite\app\VERSION.txt" >nul 2>&1

set "LANZADOR=%~dp0lanzador_satelite.bat"
if not exist "%LANZADOR%" set "LANZADOR=C:\PresupuestosSatelite\lanzador_satelite.bat"
if not exist "%LANZADOR%" (
    echo.
    echo No encontre el lanzador. Abre el acceso directo
    echo "Presupuestos Satelite" del Escritorio y listo.
    pause
    exit /b 1
)

echo Abriendo el lanzador (copia la version completa)...
start "" "%LANZADOR%"
exit /b 0
