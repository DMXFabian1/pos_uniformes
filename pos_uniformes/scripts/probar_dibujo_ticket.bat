@echo off
rem =====================================================
rem  Imprime un ticket de PRUEBA con el dibujo de temporada.
rem  Uso:  probar_dibujo_ticket.bat           (el de hoy)
rem        probar_dibujo_ticket.bat halloween
rem        probar_dibujo_ticket.bat --todas
rem =====================================================
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.probar_dibujo_ticket %*
echo.
pause
