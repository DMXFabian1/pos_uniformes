@echo off
rem Crea "POS Uniformes" y "Actualizar POS" en el Escritorio de esta PC.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0crear_accesos_principal.ps1"
pause
