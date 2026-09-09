@echo off
rem Vigia del servidor PWA: lo levanta si no esta (sin ventana). Uso: servidor_pwa_vigia.bat [--reiniciar]
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.servidor_pwa_vigia %*
