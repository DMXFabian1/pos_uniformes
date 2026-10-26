@echo off
rem =====================================================
rem  Tailscale en la PC principal: llegar a la tienda desde
rem  cualquier red (Mac y celular). Pide permiso de admin.
rem  Uso: scripts\instalar_tailscale.bat [auth-key opcional]
rem =====================================================
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile -ExecutionPolicy Bypass -NoExit -File \"%~dp0instalar_tailscale.ps1\" -AuthKey \"%~1\"'"
