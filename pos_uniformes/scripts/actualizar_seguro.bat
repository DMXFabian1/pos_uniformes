@echo off
rem Actualiza con cuidado: build -> respaldo -> migraciones -> publicar, con
rem vuelta atras si algo falla (scripts\actualizar.py). Lo llaman
rem actualizar_pc_principal.bat y abrir_pos.bat, que ya trajeron lo nuevo.
rem Devuelve 1 si algo no quedo. Uso: [--al-abrir] [--traer] [--estado]
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.actualizar %*
exit /b %ERRORLEVEL%
