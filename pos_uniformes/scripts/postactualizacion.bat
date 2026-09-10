@echo off
rem Deja tareas y servicios al dia despues de actualizar (lo llaman abrir_pos.bat
rem y actualizar_pc_principal.bat). Idempotente y silencioso. Uso: [--forzar]
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.postactualizacion %*
exit /b 0
