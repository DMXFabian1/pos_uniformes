@echo off
rem =====================================================
rem  Servidor de impresion SIN ventana.
rem
rem  Saca de la cola los tickets, etiquetas y hojas de
rem  conteo que mandan las demas PCs, sin que el kiosko
rem  este abierto. Solo corre en la PC marcada como
rem  "Servidor de impresion" (menu admin del kiosko).
rem
rem  Lo arranca la tarea "POS Impresion" al iniciar sesion.
rem  A mano:
rem    servidor_impresion.bat            se queda corriendo
rem    servidor_impresion.bat --drenar   saca lo que haya y termina
rem =====================================================
setlocal
cd /d "%~dp0..\.."
set PYTHONIOENCODING=utf-8
"%~dp0..\.venv\Scripts\python.exe" -m pos_uniformes.scripts.servidor_impresion %*
exit /b %ERRORLEVEL%
