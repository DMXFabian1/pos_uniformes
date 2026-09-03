@echo off
rem =====================================================
rem  UNA SOLA VEZ en la PC principal, como ADMINISTRADOR
rem  (clic derecho - Ejecutar como administrador)
rem  Prepara la carpeta compartida de updates para kioskos
rem =====================================================

if not exist C:\pos_updates mkdir C:\pos_updates

echo Creando el share (si ya existe, el error es normal)...
net share pos_updates=C:\pos_updates

echo Abriendo el puerto de compartir archivos en el firewall...
netsh advfirewall firewall add rule name="SMB pos_updates" dir=in action=allow protocol=TCP localport=445

echo.
echo ==============================================================
echo  Falta SOLO un paso a mano (4 clics, sin escribir nada):
echo  Panel de control - Centro de redes y recursos compartidos -
echo  Configuracion de uso compartido avanzado:
echo    - Perfil Privado: ACTIVAR deteccion de redes
echo                      ACTIVAR compartir archivos e impresoras
echo    - Todas las redes: DESACTIVAR el uso compartido con
echo                       proteccion por contrasena
echo  Y el perfil de red de Ethernet debe estar en PRIVADA.
echo ==============================================================
pause
