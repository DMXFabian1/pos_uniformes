@echo off
rem =====================================================
rem  Quita el parpadeo de la ventana negra: vuelve a crear
rem  las tareas de Windows del POS para que corran ocultas
rem  (via correr_oculto.vbs). No cambia horarios ni nada mas.
rem  Uso: scripts\quitar_parpadeo_tareas.bat
rem =====================================================
setlocal
cd /d "%~dp0.."

echo === Bot y PWA: un solo supervisor oculto (sustituye a las 4 tareas de cada 5 min) ===
call "%~dp0instalar_supervisor.bat" sinpausa

rem Las diarias de hora fija (las de Telegram y el corte) tambien parpadeaban.
rem "POS Resumen diario" no se toca: esa lleva una hora que tu elegiste.
for %%T in ("POS Resumen 1645 16:45 --si-toca" "POS Resumen 1745 17:45 --si-toca" "POS Pendientes 13:30 --pendientes") do (
    for /f "tokens=1,2,3,4,5" %%a in (%%T) do (
        schtasks /Query /TN "%%a %%b %%c" >nul 2>&1
        if not errorlevel 1 (
            schtasks /Create /F /TN "%%a %%b %%c" /SC DAILY /ST %%d /TR "wscript.exe \"%~dp0correr_oculto.vbs\" resumen_diario_telegram.bat %%e" >nul
            if not errorlevel 1 echo   %%a %%b %%c - ok
        )
    )
)
for %%T in ("POS Corte 1630 16:30" "POS Corte 1730 17:30") do (
    for /f "tokens=1,2,3,4" %%a in (%%T) do (
        schtasks /Query /TN "%%a %%b %%c" >nul 2>&1
        if not errorlevel 1 (
            schtasks /Create /F /TN "%%a %%b %%c" /SC DAILY /ST %%d /TR "wscript.exe \"%~dp0correr_oculto.vbs\" corte_automatico.bat" >nul
            if not errorlevel 1 echo   %%a %%b %%c - ok
        )
    )
)

echo.
echo ============================================
echo  LISTO. Ya no debe aparecer el recuadro negro.
echo ============================================
pause
exit /b 0
