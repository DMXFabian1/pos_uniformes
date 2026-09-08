@echo off
rem Corte automatico 30 min antes de cerrar. Lo llaman las tareas "POS Corte 16:30" y "POS Corte 17:30".
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.corte_automatico %*
endlocal
