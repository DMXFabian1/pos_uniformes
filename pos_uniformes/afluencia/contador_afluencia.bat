@echo off
rem Contador de afluencia (PC servidor). Reinicia solo si se cae.
cd /d %~dp0
:loop
.venv\Scripts\python contador_afluencia.py
echo El contador termino, reiniciando en 15 s...
timeout /t 15 /nobreak >nul
goto loop
