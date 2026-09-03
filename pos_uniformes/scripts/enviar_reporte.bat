@echo off
rem =====================================================
rem  Manda a Claude lo que dijo la consola (por git).
rem  Sube todo lo que haya en la carpeta reportes\:
rem   - reportes\ultimo_update.log (lo guarda solo el actualizador)
rem   - reportes\mensaje.txt (texto libre: escribelo con
rem     notepad reportes\mensaje.txt, pega ahi lo que sea)
rem  Uso: scripts\enviar_reporte.bat
rem =====================================================
setlocal
cd /d "%~dp0.."

if not exist reportes mkdir reportes

git add reportes
git commit -m "reporte: consola de la PC principal %date% %time%"
if errorlevel 1 (
    echo.
    echo No habia nada nuevo que mandar en la carpeta reportes\.
    pause
    exit /b 0
)
git push
if errorlevel 1 (
    echo.
    echo *** No se pudo subir (revisa internet) - reintenta en un momento ***
    pause
    exit /b 1
)
echo.
echo ============================================
echo  Reporte enviado. Dile a Claude:
echo  "ya te mande el reporte" y el lo lee alla.
echo ============================================
pause
