@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Scalper Polymarket - correr
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0CORRER.ps1" %*
echo.
pause
