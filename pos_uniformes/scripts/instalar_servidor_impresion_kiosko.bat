@echo off
rem =====================================================
rem  Deja el KIOSKO imprimiendo aunque este cerrado.
rem
rem  Se corre EN EL KIOSKO (el que tiene las impresoras de
rem  etiquetas). Aqui no hay Python ni repo: solo el .exe,
rem  asi que el servidor de impresion es el mismo programa
rem  arrancado con --servidor-impresion.
rem
rem  Se copia solo a C:\pos_updates con cada build, asi que
rem  en el kiosko se corre desde la carpeta compartida.
rem =====================================================
setlocal

set APP=C:\PresupuestosSatelite
set EXE=
for %%F in ("%APP%\app\*.exe") do set EXE=%%~fF
if not defined EXE for %%F in ("%APP%\*.exe") do set EXE=%%~fF
if not defined EXE goto :sin_exe

echo Usando: %EXE%
echo.
echo === Probando: saco de la cola lo que haya ===
"%EXE%" --servidor-impresion --drenar
if errorlevel 2 goto :no_es_servidor

echo.
echo === Tarea "POS Impresion kiosko" (al iniciar sesion) ===
schtasks /Create /F /TN "POS Impresion kiosko" /SC ONLOGON /TR "\"%EXE%\" --servidor-impresion" >nul
if errorlevel 1 goto :error
echo   Creada.

echo === Vigia "POS Impresion kiosko vigia" (cada 5 min) ===
rem Si el proceso se muere a media mañana, la tarea de inicio de sesion no lo
rem levanta hasta el proximo login: un dia entero sin que salga papel. El
rem candado del programa hace que los lanzamientos de mas no hagan nada.
schtasks /Create /F /TN "POS Impresion kiosko vigia" /SC MINUTE /MO 5 /TR "\"%EXE%\" --servidor-impresion" >nul
if errorlevel 1 goto :error
echo   Creado.

echo.
echo === Arrancandolo ahora ===
start "" "%EXE%" --servidor-impresion
echo   Listo. Corre sin ventana: no hay nada que cerrar por accidente.
echo.
echo   El kiosko se puede abrir y cerrar como siempre; esto es aparte.
echo   Para ver que hace:  type "%%LOCALAPPDATA%%\PresupuestosSatelite\logs\servidor_impresion.log"
echo   Y /pulso en el bot dice si quedo algo sin imprimir.
echo.
pause
exit /b 0

:sin_exe
echo.
echo *** No encontre el .exe del satelite en %APP% ***
echo     Abre el kiosko una vez (lanzador_satelite.bat) y vuelve a correr esto.
pause
exit /b 1

:no_es_servidor
echo.
echo *** Esta PC esta marcada como "Estacion", no como "Servidor de impresion". ***
echo     Abre el kiosko - menu admin (Ctrl+Shift+A) - "Rol de impresion de esta PC"
echo     y elige "Servidor de impresion". Luego vuelve a correr este instalador.
pause
exit /b 2

:error
echo.
echo *** No se pudo crear la tarea de Windows - corre esto como administrador ***
pause
exit /b 1
