@echo off
rem =====================================================
rem  ¿Por que un prestamo no se descuenta del sueldo?
rem
rem  Enseña cada prestamo y en que estado quedo, y cuanto
rem  se le va a descontar de verdad en el siguiente pago.
rem  No cambia nada: solo mira.
rem =====================================================
setlocal
cd /d "%~dp0..\.."

chcp 65001 >nul
set PYTHONIOENCODING=utf-8

if not exist "pos_uniformes\reportes" mkdir "pos_uniformes\reportes"
set REPORTE=pos_uniformes\reportes\prestamos.txt

echo Revisando los prestamos...
echo.
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.revisar_prestamos > "%REPORTE%" 2>&1
type "%REPORTE%"
echo.
echo (Tambien quedo guardado en %REPORTE%)
pause
