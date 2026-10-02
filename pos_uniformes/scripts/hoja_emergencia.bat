@echo off
rem =====================================================
rem  Genera la hoja "Si algo falla" para pegar junto a la
rem  caja, y la abre para imprimir (Ctrl+P, una hoja).
rem =====================================================
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.hoja_emergencia --abrir
pause
