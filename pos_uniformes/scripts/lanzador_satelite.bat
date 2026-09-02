@echo off
rem Lanzador del satelite con auto-actualizacion por red.
rem Este .bat es el acceso directo del kiosko; la logica vive en el .ps1.
powershell -ExecutionPolicy Bypass -File "%~dp0lanzador_satelite.ps1"
