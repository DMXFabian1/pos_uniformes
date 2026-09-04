@echo off
rem =====================================================
rem  Abre el POS principal buscando actualizaciones antes
rem  (mismo espiritu que el lanzador de los kioskos):
rem   - sin actualizaciones: abre al instante
rem   - con actualizaciones: pull + migraciones + build
rem     (publica a kioskos) y luego abre
rem   - sin internet o con error: abre la version actual
rem =====================================================
setlocal
cd /d "%~dp0.."

echo Buscando actualizaciones...
git fetch origin
if errorlevel 1 (
    echo Sin internet o sin acceso al repositorio - abriendo la version actual.
    goto :launch
)

set BEHIND=0
for /f %%c in ('git rev-list HEAD..@{u} --count 2^>nul') do set BEHIND=%%c
if "%BEHIND%"=="0" (
    echo Ya estas al dia.
    goto :launch
)

echo Hay %BEHIND% actualizacion(es). Aplicando...
git pull
if errorlevel 1 (
    echo *** Fallo el pull - abriendo la version actual. Manda reporte con enviar_reporte.bat ***
    timeout /t 6 >nul
    goto :launch
)

echo Aplicando migraciones...
.\.venv\Scripts\python.exe -m alembic upgrade head
if errorlevel 1 (
    echo *** Fallo la migracion - abriendo de todas formas. Manda reporte. ***
    timeout /t 6 >nul
    goto :launch
)

echo Build del satelite y publicacion a kioskos (unos minutos)...
call scripts\build_presupuestos_satelite_windows.bat
if errorlevel 1 (
    echo *** Fallo la build del satelite - el POS abre igual. Manda reporte. ***
    timeout /t 6 >nul
)

:launch
start "" .venv\Scripts\pythonw.exe main.py
exit /b 0
