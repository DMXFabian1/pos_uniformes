@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
title Actualizar - Scalper Polymarket

echo.
echo  Si el bot esta corriendo, cierra su ventana con Ctrl+C antes de continuar.
echo.
pause

where git >nul 2>&1
if errorlevel 1 (
  echo  Git no esta instalado. Descarga el ZIP de nuevo desde GitHub o instala Git.
  pause
  exit /b 1
)

echo.
echo  1/2  Descargando la ultima version...
git pull
if errorlevel 1 (
  echo.
  echo  git pull fallo. Si tienes cambios locales, guardalos o descartalos con:
  echo    git stash
  pause
  exit /b 1
)

echo.
echo  2/2  Actualizando dependencias...
echo  Limpiando restos de instalaciones interrumpidas...
for /d %%D in (".venv\Lib\site-packages\~*") do rmdir /s /q "%%D" 2>nul

if not exist ".venv\Scripts\python.exe" (
  echo  No hay entorno virtual. Ejecuta primero:
  echo    powershell -ExecutionPolicy Bypass -File deploy\instalar-windows.ps1
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pip install --quiet -e ".[learn]"
if errorlevel 1 (
  echo  Fallo la instalacion de dependencias.
  pause
  exit /b 1
)

echo.
echo  Listo. Version actualizada.
echo  Abre INICIAR-TODO.bat para arrancar el bot y el panel.
echo.
pause
