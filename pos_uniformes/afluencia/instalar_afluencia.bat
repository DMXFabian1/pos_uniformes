@echo off
rem =====================================================
rem  Instala el contador de afluencia en ESTA PC (servidor):
rem  entorno propio + modelo + config + tarea OCULTA al iniciar sesion.
rem  Uso: afluencia\instalar_afluencia.bat   (una sola vez; repetirlo no dana)
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
rem Las lineas las dibuja Daniel en esta PC con dibujar_lineas.bat; el
rem ejemplo solo sirve la primera vez. Nunca se pisa lo que el dibujo.
if not exist afluencia.json (
    copy afluencia.json.example afluencia.json >nul
    echo   Creado afluencia.json desde el ejemplo.
) else (
    echo   Ya existe afluencia.json, se conserva. Para mover lineas: afluencia\dibujar_lineas.bat
)

echo.
echo === 2b/4 Deteniendo el contador que ya corria (si hay) ===
rem El contador solo lee afluencia.json al arrancar; hay que bajarlo para
rem que tome la linea nueva. Se cierran el bucle .bat y su python.
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like '*contador_afluencia*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo   Listo.

echo.
echo === 3/4 Prueba de conexion con el DVR (cuadros de calibracion) ===
.venv\Scripts\python contador_afluencia.py --calibrar
if errorlevel 1 goto :error
echo   Revisa la carpeta calibracion\ : la linea roja debe cruzar la puerta.

echo.
echo === 4/4 Tarea de Windows: arranca solo al iniciar sesion, SIN ventana ===
rem Va por scripts\correr_oculto.vbs: la version anterior abria una consola
rem que habia que dejar abierta (y que se cerraba sin querer).
schtasks /Create /F /TN "POS Afluencia" /SC ONLOGON /TR "wscript.exe \"%~dp0..\scripts\correr_oculto.vbs\" ..\afluencia\contador_afluencia.bat" >nul
if errorlevel 1 (
    echo   No se pudo crear la tarea programada; corre este .bat como administrador.
) else (
    echo   Tarea "POS Afluencia" creada (oculta).
)

echo.
echo ============================================
echo  LISTO. Arrancando el contador ahora, oculto.
echo  Lo que hace queda en logs\afluencia.log.
echo  Para revisarlo: afluencia\diagnostico_afluencia.bat
echo ============================================
wscript.exe "%~dp0..\scripts\correr_oculto.vbs" ..\afluencia\contador_afluencia.bat
exit /b 0

:error
echo.
echo *** ALGO FALLO - corre afluencia\diagnostico_afluencia.bat y manda el reporte ***
pause
exit /b 1
