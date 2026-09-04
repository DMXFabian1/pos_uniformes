@echo off
rem =====================================================
rem  Instala el KIOSKO (satelite) en ESTA PC, completo:
rem  lanzador + acceso directo en Escritorio + app.
rem  Sirve en la PC principal (usa C:\pos_updates local)
rem  y en cualquier kiosko (usa la carpeta de red).
rem =====================================================
setlocal

set ORIGEN=C:\pos_updates
if exist "%ORIGEN%\lanzador_satelite.bat" goto :instalar

rem No es la PC principal: ir por red (con la credencial del kiosko)
net use \\192.168.0.10\pos_updates pos2026 /user:kiosko /persistent:no >nul 2>&1
set ORIGEN=\\192.168.0.10\pos_updates
if exist "%ORIGEN%\lanzador_satelite.bat" goto :instalar

echo No se encontro la carpeta de updates (ni local ni en red).
echo En la PC principal corre primero: scripts\actualizar_pc_principal.bat
pause
exit /b 1

:instalar
if not exist C:\PresupuestosSatelite mkdir C:\PresupuestosSatelite
copy /Y "%ORIGEN%\lanzador_satelite.bat" C:\PresupuestosSatelite\ >nul
copy /Y "%ORIGEN%\lanzador_satelite.ps1" C:\PresupuestosSatelite\ >nul
echo Lanzador instalado desde: %ORIGEN%
echo Abriendo el satelite (descarga la app y crea su acceso directo)...
start "" C:\PresupuestosSatelite\lanzador_satelite.bat
exit /b 0
