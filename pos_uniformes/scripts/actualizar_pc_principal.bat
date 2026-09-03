@echo off
rem =====================================================
rem  Actualiza el POS en la PC principal (todo en uno):
rem  git pull + migraciones + build + publicar a kioskos
rem  Uso: scripts\actualizar_pc_principal.bat
rem =====================================================
setlocal
cd /d "%~dp0.."

echo === 1/3 Trayendo lo nuevo del repositorio ===
git pull
if errorlevel 1 goto :error

echo.
echo === 2/3 Aplicando migraciones de base de datos ===
.\.venv\Scripts\python.exe -m alembic upgrade head
if errorlevel 1 goto :error

echo.
echo === 3/3 Build del satelite (publica solo a los kioskos) ===
call scripts\build_presupuestos_satelite_windows.bat
if errorlevel 1 goto :error

echo.
echo ============================================
echo  LISTO. Version publicada para kioskos:
if exist C:\pos_updates\PresupuestosSatelite\VERSION.txt (
    type C:\pos_updates\PresupuestosSatelite\VERSION.txt
) else (
    echo  (no se encontro C:\pos_updates - revisa el share)
)
echo ============================================
pause
exit /b 0

:error
echo.
echo *** ALGO FALLO - toma foto de este error y mandala ***
pause
exit /b 1
