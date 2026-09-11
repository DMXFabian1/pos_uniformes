# Abre el panel web y lo muestra en el navegador. El bot puede estar corriendo o no.
$ErrorActionPreference = "Stop"
$proyecto = Split-Path -Parent $PSScriptRoot
Set-Location $proyecto
$env:PYTHONUTF8 = "1"                      # Python escribe UTF-8
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }   # y la consola lo muestra bien
$exe = Join-Path $proyecto ".venv\Scripts\scalper.exe"
if (-not (Test-Path $exe)) { Write-Host "Falta instalar: ejecuta deploy\instalar-windows.ps1" -ForegroundColor Red; exit 1 }
Start-Job -ScriptBlock { Start-Sleep 2; Start-Process "http://127.0.0.1:8787" } | Out-Null
Write-Host "panel en http://127.0.0.1:8787  (Ctrl+C para cerrarlo)" -ForegroundColor Green
& $exe -c config.yaml dashboard
