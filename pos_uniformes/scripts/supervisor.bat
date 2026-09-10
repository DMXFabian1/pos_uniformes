@echo off
rem Supervisor del POS (bot de Telegram + servidor PWA), un solo proceso oculto.
rem Uso: supervisor.bat [--reiniciar | --pedir-reinicio]
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.supervisor %*
