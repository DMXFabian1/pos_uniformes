@echo off
rem =====================================================
rem  Abre el POS principal buscando actualizaciones antes
rem  (mismo espiritu que el lanzador de los kioskos):
rem   - sin actualizaciones: abre al instante
rem   - con actualizaciones: pull + migraciones + build
rem     (publica a kioskos) y luego abre
rem   - si lo que corren los kioskos quedo atras del codigo
rem     (por ejemplo tras un pull a mano), tambien publica
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
    goto :revisar_publicado
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

:build
echo Build del satelite y publicacion a kioskos (unos minutos)...
call scripts\build_presupuestos_satelite_windows.bat
if errorlevel 1 (
    echo *** Fallo la build del satelite - el POS abre igual. Manda reporte. ***
    timeout /t 6 >nul
)
goto :launch

rem ---------------------------------------------------------------
rem  Ya al dia con el repositorio, pero lo que corren los kioskos
rem  puede ser mas viejo: pasa cuando se hizo `git pull` a mano o
rem  cuando una build fallo. Si el commit publicado no es el de
rem  ahora, se vuelve a publicar. (2026-09-22: por eso salio
rem  "Base de datos no lista" en la principal.)
rem ---------------------------------------------------------------
:revisar_publicado
set UPDATES=%POS_UNIFORMES_UPDATES_DIR%
if "%UPDATES%"=="" set UPDATES=C:\pos_updates
if not exist "%UPDATES%\PresupuestosSatelite\VERSION.txt" goto :launch
set PUBLICADO=
set /p PUBLICADO=<"%UPDATES%\PresupuestosSatelite\VERSION.txt"
if "%PUBLICADO%"=="" goto :launch
set AHORA=
for /f %%h in ('git rev-parse --short HEAD 2^>nul') do set AHORA=%%h
if "%AHORA%"=="" goto :launch
echo %PUBLICADO% | find /I "%AHORA%" >nul
if errorlevel 1 (
    echo Los kioskos corren %PUBLICADO% y el codigo va en %AHORA% - republicando...
    goto :build
)
echo Los kioskos ya tienen lo de ahora ^(%PUBLICADO%^).

:launch
rem Siempre: si la infraestructura ya esta al dia no toca nada (es barato).
call scripts\postactualizacion.bat
start "" .venv\Scripts\pythonw.exe main.py
exit /b 0
