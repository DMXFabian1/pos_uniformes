@echo off
rem =====================================================
rem  Deja el servidor de impresion corriendo en ESTA PC
rem  (la que tiene las impresoras conectadas).
rem
rem  Desde que existe esto, el papel sale aunque el kiosko
rem  este cerrado: antes el despachador vivia dentro de la
rem  ventana del kiosko y apagarlo dejaba todo en la cola.
rem
rem  Uso: scripts\instalar_servidor_impresion.bat
rem =====================================================
setlocal
cd /d "%~dp0.."

echo === Revisando que esta PC sea el Servidor de impresion ===
call "%~dp0servidor_impresion.bat" --drenar
if errorlevel 2 goto :no_es_servidor
if errorlevel 1 goto :error

echo.
echo === Tarea de Windows "POS Impresion" (al iniciar sesion) ===
schtasks /Create /F /TN "POS Impresion" /SC ONLOGON /TR "wscript.exe \"%~dp0correr_oculto.vbs\" servidor_impresion.bat" >nul
if errorlevel 1 goto :error
echo   Creada. Se arranca sola cada vez que entras a Windows.

echo === Vigia "POS Impresion vigia" (cada 5 min) ===
rem Si el proceso se muere (o Windows lo mata), la tarea ONLOGON no lo
rem levanta hasta el proximo inicio de sesion, y eso aqui significa un dia
rem entero sin que salga papel. El vigia lo relanza; el candado del propio
rem programa hace que los lanzamientos de mas no hagan nada.
schtasks /Create /F /TN "POS Impresion vigia" /SC MINUTE /MO 5 /TR "wscript.exe \"%~dp0correr_oculto.vbs\" servidor_impresion.bat" >nul
if errorlevel 1 goto :error
echo   Creado. Si el servidor se cae, vuelve solo en 5 min o menos.
echo.
echo === Arrancandolo ahora, sin esperar a reiniciar ===
wscript.exe "%~dp0correr_oculto.vbs" servidor_impresion.bat
echo   Listo. Corre oculto: no hay ventana que cerrar por accidente.
echo.
echo   Para ver que esta haciendo:  type pos_uniformes\logs\servidor_impresion.log
echo   Para saber si algo se quedo sin imprimir, manda /pulso al bot.
echo.
pause
exit /b 0

:no_es_servidor
echo.
echo *** Esta PC esta marcada como "Estacion", no como "Servidor de impresion". ***
echo     Una estacion no tiene impresoras: si despachara, reclamaria los trabajos
echo     de las demas y los mandaria a una impresora que no existe.
echo.
echo     Abre el kiosko - menu admin - "Rol de impresion de esta PC" y elige
echo     "Servidor de impresion". Luego vuelve a correr este instalador.
echo.
pause
exit /b 2

:error
echo.
echo *** ALGO FALLO - revisa el mensaje de arriba ***
pause
exit /b 1
