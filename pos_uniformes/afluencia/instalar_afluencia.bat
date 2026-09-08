@echo off
rem =====================================================
rem  Instala el contador de afluencia en ESTA PC (servidor):
rem  entorno propio + modelo + config + tarea al iniciar sesion.
rem  Uso: afluencia\instalar_afluencia.bat   (una sola vez)
rem =====================================================
setlocal
cd /d "%~dp0"

echo === 1/4 Entorno de Python para el contador (aparte del POS) ===
if not exist .venv (
    py -3.12 -m venv .venv || python -m venv .venv
    if errorlevel 1 goto :error
)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo === 2/4 Configuracion de camaras y lineas ===
if not exist afluencia.json (
    copy afluencia.json.example afluencia.json >nul
    echo   Creado afluencia.json desde el ejemplo.
) else (
    echo   Ya existe afluencia.json, se conserva.
)

echo.
echo === 3/4 Prueba de conexion con el DVR (cuadros de calibracion) ===
.venv\Scripts\python contador_afluencia.py --calibrar
if errorlevel 1 goto :error
echo   Revisa la carpeta calibracion\ : la linea roja debe cruzar la puerta.

echo.
echo === 4/4 Tarea de Windows: arranca solo al iniciar sesion ===
schtasks /Create /F /TN "POS Afluencia" /SC ONLOGON /TR "\"%~dp0contador_afluencia.bat\"" >nul
if errorlevel 1 (
    echo   No se pudo crear la tarea programada; puedes abrir contador_afluencia.bat a mano.
) else (
    echo   Tarea "POS Afluencia" creada.
)

echo.
echo ============================================
echo  LISTO. Arrancando el contador ahora...
echo  (Deja esta ventana abierta; cuenta y guarda cada minuto.)
echo ============================================
start "POS Afluencia" "%~dp0contador_afluencia.bat"
exit /b 0

:error
echo.
echo *** ALGO FALLO - toma foto de este error y mandala ***
pause
exit /b 1
