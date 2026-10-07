@echo off
rem =====================================================
rem  Imprime una prueba del logo en la impresora de
rem  tickets, y nada mas. Para ver si las serifas finas
rem  sobreviven a la termica antes de rehacer el ticket.
rem =====================================================
setlocal
cd /d "%~dp0..\.."
set PYTHONIOENCODING=utf-8
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.probar_logo_ticket
echo.
pause
