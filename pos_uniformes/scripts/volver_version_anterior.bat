@echo off
rem =====================================================
rem  Los kioskos vuelven a la version anterior.
rem  Para cuando la version nueva salio mala: intercambia
rem  lo publicado con lo que habia antes. Cada kiosko la
rem  toma al abrir (o con "Buscar actualizaciones").
rem  Correrlo otra vez deshace el cambio.
rem  La base NO se regresa: un kiosko viejo abre igual.
rem =====================================================
setlocal
call "%~dp0actualizar_seguro.bat" --volver
echo.
pause
exit /b 0
