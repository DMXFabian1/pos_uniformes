@echo off
rem =====================================================
rem  Alta del producto "Bata Infantil Plastificada" ($75)
rem  8 colores, talla Uni, stock 0 (se cuenta despues).
rem  Uso: scripts\alta_bata_plastificada.bat
rem =====================================================
setlocal
cd /d "%~dp0.."

echo === Trayendo lo nuevo del repositorio ===
git pull
if errorlevel 1 goto :error

echo.
echo === Dando de alta el producto ===
set PYTHONPATH=%CD%\..
.\.venv\Scripts\python.exe scripts\alta_bata_infantil_plastificada.py
if errorlevel 1 goto :error

echo.
echo ============================================
echo  LISTO. Ya aparece en el POS al buscar "plastificada".
echo ============================================
pause
exit /b 0

:error
echo.
echo *** ALGO FALLO - toma foto de este error y mandala ***
pause
exit /b 1
