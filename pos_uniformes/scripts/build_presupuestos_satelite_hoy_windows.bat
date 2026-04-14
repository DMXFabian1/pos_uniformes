@echo off
setlocal

cd /d "%~dp0.."

echo ==========================================
echo  Build app satelite de Presupuestos
echo ==========================================
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0build_presupuestos_satelite_windows.ps1" -WithPrecheck
set "BUILD_EXIT=%ERRORLEVEL%"

echo.
if not "%BUILD_EXIT%"=="0" (
    echo La build satelite fallo con codigo %BUILD_EXIT%.
    exit /b %BUILD_EXIT%
)

echo Build terminada.
echo Revisa la carpeta dist\ y el ZIP generado.
exit /b 0
