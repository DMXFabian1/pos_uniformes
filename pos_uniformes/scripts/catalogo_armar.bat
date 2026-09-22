@echo off
rem =====================================================
rem  Catalogo (fases 2 y 3), los tres pasos en orden:
rem    1. armar_uniformes        - el uniforme de cada escuela
rem    2. crear_piezas_faltantes - pants suelto / playera que faltan
rem    3. armar_recetas          - de que se arma cada 3pz y chamarra
rem
rem  Sin argumentos solo ensena que haria (no escribe nada).
rem  Con --aplicar lo hace, en ese orden.
rem
rem  Uso:  scripts\catalogo_armar.bat
rem        scripts\catalogo_armar.bat --aplicar
rem =====================================================
setlocal
cd /d "%~dp0..\.."
set PY="%~dp0..\.venv\Scripts\python.exe"

echo === 1/3 Uniformes por escuela ===
%PY% -m pos_uniformes.scripts.armar_uniformes %*
if errorlevel 1 goto :error

echo.
echo === 2/3 Piezas que faltan (pants suelto / playera) ===
%PY% -m pos_uniformes.scripts.crear_piezas_faltantes %*
if errorlevel 1 goto :error

echo.
echo === 3/3 Recetas de los conjuntos ===
%PY% -m pos_uniformes.scripts.armar_recetas %*
if errorlevel 1 goto :error

echo.
if "%~1"=="" (
  echo Eso es lo que HARIA. Para aplicarlo:  scripts\catalogo_armar.bat --aplicar
) else (
  echo LISTO. Revisa en el POS: Mas ^> Uniformes por escuela.
)
pause
exit /b 0

:error
echo.
echo Algo fallo. Manda la pantalla o corre scripts\enviar_reporte.bat
pause
exit /b 1
