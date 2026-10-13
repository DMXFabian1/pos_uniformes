@echo off
rem =====================================================
rem  Imprime el mismo ticket largo con franjas de 128, 256 y 512
rem  (y uno de texto) para escoger el que salga completo y de corrido.
rem  Uso:  probar_velocidad_ticket.bat
rem        probar_velocidad_ticket.bat --guardar 256
rem =====================================================
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.probar_velocidad_ticket %*
echo.
pause
