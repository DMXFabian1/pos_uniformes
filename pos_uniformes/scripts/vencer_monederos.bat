@echo off
rem =====================================================
rem  Proceso diario del monedero de clientes: asienta el
rem  saldo vencido y repone cashback que no se acredito.
rem  Lo corre la tarea "POS Monederos" cada noche.
rem =====================================================
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.vencer_monederos %*
exit /b %ERRORLEVEL%
