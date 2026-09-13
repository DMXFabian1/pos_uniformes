@echo off
rem Dibujar las lineas de conteo con el raton, encima del cuadro de cada camara.
rem 1) toma un cuadro fresco de cada camara (DVR)  2) abre la ventana para dibujar.
rem Al guardar, el contador que corre oculto toma las lineas nuevas solo.
setlocal
cd /d "%~dp0"
if not exist afluencia.json (
    echo Primero corre afluencia\instalar_afluencia.bat
    pause
    exit /b 1
)
echo Tomando un cuadro de cada camara...
.venv\Scripts\python contador_afluencia.py --calibrar
if errorlevel 1 (
    echo No se pudo hablar con el DVR. Revisa que este prendido y corre afluencia\diagnostico_afluencia.bat
    pause
    exit /b 1
)
"%~dp0..\.venv\Scripts\python.exe" dibujar_lineas.py
