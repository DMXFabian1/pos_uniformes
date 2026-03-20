@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0build_presupuestos_satelite_windows.ps1" %*
endlocal
