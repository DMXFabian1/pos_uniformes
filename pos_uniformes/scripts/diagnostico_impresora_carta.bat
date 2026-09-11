@echo off
rem ¿Por que no imprime la hoja carta? Deja el reporte en reportes\impresora_carta.txt
rem y manda una hoja de prueba a cada impresora HP. Luego: scripts\enviar_reporte.bat
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.diagnostico_impresora_carta %*
pause
