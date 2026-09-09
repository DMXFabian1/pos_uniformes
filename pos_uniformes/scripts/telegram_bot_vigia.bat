@echo off
rem Vigia del bot de Telegram: lo levanta si no esta (sin ventana). Uso: telegram_bot_vigia.bat [--reiniciar]
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.telegram_bot_vigia %*
