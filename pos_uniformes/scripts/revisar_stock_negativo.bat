@echo off
rem =====================================================
rem  ¿Que tallas dicen tener menos que nada?
rem
rem  Una talla en negativo es la tienda avisando que se
rem  vendio algo que nadie habia contado. Este guion las
rem  busca, guarda la lista en reportes\ y te pregunta si
rem  la manda a Claude.
rem
rem  Sin argumentos SOLO MIRA. Para subirlas a cero:
rem      scripts\revisar_stock_negativo.bat --aplicar
rem  (subirlas a cero no arregla el inventario: lo que
rem   lo arregla es contarlas. La lista sale en orden.)
rem =====================================================
setlocal
cd /d "%~dp0..\.."

rem La consola de Windows abre en la pagina vieja (850) y ahi los acentos se
rem guardan rotos: "Sueter" salia como "SuUter" en el reporte. Con 65001 y
rem PYTHONIOENCODING el archivo queda en UTF-8, que es como lo lee la Mac.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

if not exist "pos_uniformes\reportes" mkdir "pos_uniformes\reportes"
set REPORTE=pos_uniformes\reportes\stock_negativo.txt

echo Revisando el inventario...
echo.
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.revisar_stock_negativo %* > "%REPORTE%" 2>&1
if errorlevel 1 (
    echo.
    echo *** No se pudo revisar. Lo que dijo la consola quedo en: ***
    echo     %REPORTE%
    type "%REPORTE%"
    pause
    exit /b 1
)

type "%REPORTE%"
echo.
echo ============================================
echo  La lista quedo guardada en:
echo    %REPORTE%
echo ============================================
echo.
set /p MANDAR=Se la mando a Claude? (s/n):
if /i "%MANDAR%"=="s" call "%~dp0enviar_reporte.bat"

pause
