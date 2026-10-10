@echo off
rem =====================================================
rem  Informe general de las finanzas de la tienda.
rem  Lo deja en reportes\finanzas.txt y lo sube por git
rem  para que Claude lo lea desde la Mac.
rem  Uso: scripts\informe_finanzas.bat [dias]   (90 por omision)
rem =====================================================
setlocal
cd /d "%~dp0.."

set DIAS=90
if not "%~1"=="" set DIAS=%~1

echo Armando el informe de los ultimos %DIAS% dias...
.\.venv\Scripts\python.exe -m pos_uniformes.scripts.informe_finanzas %DIAS%
if errorlevel 1 (
    echo.
    echo *** No se pudo armar el informe (revisa que la base responda^) ***
    pause
    exit /b 1
)

git add reportes\finanzas.txt
git commit -m "reporte: finanzas %date% %time%" >nul 2>&1
git push
if errorlevel 1 (
    echo.
    echo *** El informe quedo en reportes\finanzas.txt pero no se pudo subir ***
    echo *** (revisa internet y corre scripts\enviar_reporte.bat^)          ***
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Informe enviado. Dile a Claude:
echo  "ya te mande el informe de finanzas".
echo ============================================
pause
