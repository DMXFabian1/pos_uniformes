@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\pythonw.exe" (
  echo Falta instalar. Ejecuta deploy\instalar-windows.ps1
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m scalper.cli -c config.yaml gui
