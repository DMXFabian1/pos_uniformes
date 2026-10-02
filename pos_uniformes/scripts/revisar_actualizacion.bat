@echo off
rem =====================================================
rem  ¿Por que no baja nada con el acceso directo?
rem  Dice en que rama esta esta copia, a cual mira, que le
rem  falta, y el comando exacto que lo arregla.
rem =====================================================
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.revisar_actualizacion
echo.
pause
