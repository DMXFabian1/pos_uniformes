@echo off
rem Descuenta del stock las ventas de la Libreta anteriores al 2026-09-14 (una sola vez).
rem Sin argumentos solo ensena que haria; con --aplicar lo hace.
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.descontar_ventas_pasadas %*
pause
