@echo off
rem =====================================================
rem  ¿Hay respaldo de la base, y sirve?
rem
rem  Un respaldo que nunca se restauro no es un respaldo,
rem  es un archivo. Esto enseña cuando fue el ultimo y
rem  LO RESTAURA en una base de juguete para probar que
rem  de verdad se puede volver de el.
rem
rem  La base de la tienda NO se toca.
rem =====================================================
setlocal
cd /d "%~dp0..\.."

chcp 65001 >nul
set PYTHONIOENCODING=utf-8

if not exist "pos_uniformes\reportes" mkdir "pos_uniformes\reportes"
set REPORTE=pos_uniformes\reportes\respaldos.txt

echo Revisando los respaldos...
echo.
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.revisar_respaldos --probar > "%REPORTE%" 2>&1
type "%REPORTE%"

echo.
echo ============================================
echo  El reporte quedo en:
echo    %REPORTE%
echo ============================================
echo.
set /p MANDAR=Se lo mando a Claude? (s/n):
if /i "%MANDAR%"=="s" call "%~dp0enviar_reporte.bat"

pause
