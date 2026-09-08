@echo off
rem Bot de Telegram (PC servidor): /corte, /estado, /resumen, /pendientes. Reinicia solo si se cae.
setlocal
cd /d "%~dp0..\.."
:loop
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.telegram_bot
echo El bot termino, reiniciando en 15 s...
timeout /t 15 /nobreak >nul
goto loop
