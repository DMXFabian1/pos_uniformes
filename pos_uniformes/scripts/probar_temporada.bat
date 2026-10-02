@echo off
rem =====================================================
rem  Finge una temporada DOS HORAS para ver el adorno
rem  antes de su fecha. Se quita solo.
rem  Uso:  probar_temporada.bat halloween
rem        probar_temporada.bat --quitar
rem        probar_temporada.bat            (como va)
rem =====================================================
setlocal
cd /d "%~dp0..\.."
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.probar_temporada %*
echo.
pause
