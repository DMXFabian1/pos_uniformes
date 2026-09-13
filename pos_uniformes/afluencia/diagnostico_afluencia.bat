@echo off
rem ¿Por que el contador de afluencia no cuenta? Deja reportes\afluencia.txt
rem Luego: scripts\enviar_reporte.bat
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.afluencia.diagnostico_afluencia %*
pause
