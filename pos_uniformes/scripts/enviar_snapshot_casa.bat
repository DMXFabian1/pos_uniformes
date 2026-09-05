@echo off
rem =====================================================
rem  Exporta el snapshot de la Libreta y lo manda a la
rem  PC de la CASA (servidor PWA siempre prendido).
rem  DESTINO: carpeta compartida de la PC de la casa,
rem  alcanzable por Tailscale (cambiar la IP de abajo).
rem =====================================================
setlocal
cd /d "%~dp0.."

set DESTINO=\\100.64.0.2\pos_movil
if not "%~1"=="" set DESTINO=%~1

echo Exportando snapshot...
.\.venv\Scripts\python.exe -m pos_uniformes.scripts.exportar_snapshot_movil data\snapshot_movil.sqlite
if errorlevel 1 (
    echo *** Fallo la exportacion ***
    exit /b 1
)

echo Enviando a %DESTINO% ...
copy /Y data\snapshot_movil.sqlite "%DESTINO%\snapshot_movil.sqlite.nuevo" >nul
if errorlevel 1 (
    echo *** No se alcanzo la PC de la casa (apagada o sin Tailscale) ***
    exit /b 1
)
rem Swap atomico del lado de la casa: el servidor nunca lee a medias.
move /Y "%DESTINO%\snapshot_movil.sqlite.nuevo" "%DESTINO%\snapshot_movil.sqlite" >nul
echo Listo: snapshot enviado.
exit /b 0
