@echo off
rem Abre el POS principal (sin ventana de consola).
cd /d "%~dp0.."
start "" .venv\Scripts\pythonw.exe main.py
