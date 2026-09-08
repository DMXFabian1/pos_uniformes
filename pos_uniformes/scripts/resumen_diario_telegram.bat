@echo off
rem Manda el resumen del dia por Telegram. Lo llama la tarea "POS Resumen diario".
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.resumen_diario_telegram %*
endlocal
