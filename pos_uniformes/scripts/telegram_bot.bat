@echo off
rem Bot de Telegram (PC servidor). Ya NO deja una ventana abierta: llama al vigia,
rem que mata el bot viejo (si hay) y levanta uno nuevo en segundo plano.
rem Log: %APPDATA%\PresupuestosSatelite\logs\telegram_bot.log (o logs\ junto al codigo).
setlocal
call "%~dp0telegram_bot_vigia.bat" --reiniciar
