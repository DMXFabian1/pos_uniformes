@echo off
rem =====================================================
rem  Imprime una prueba del logo y nada mas, para ver si
rem  sobrevive a la termica antes de rehacer el ticket.
rem
rem    probar_logo_ticket.bat          por la cola
rem    probar_logo_ticket.bat --aqui   en la impresora
rem                                    de ESTA PC
rem
rem  Para comparar dos impresoras hay que usar --aqui:
rem  por la cola no se elige en cual sale.
rem =====================================================
setlocal
cd /d "%~dp0..\.."
set PYTHONIOENCODING=utf-8
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.probar_logo_ticket %*
echo.
pause
