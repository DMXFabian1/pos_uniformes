@echo off
rem ¿Que tarea abre la ventana negra? Uso: revisar_tareas.bat [--arreglar]
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.revisar_tareas %*
pause
