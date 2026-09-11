# Arranca el bot en modo paper trading (recolecta, simula y reentrena). Ctrl+C para detenerlo:
# el cierre guarda en disco lo que esté pendiente.
$ErrorActionPreference = "Stop"
$proyecto = Split-Path -Parent $PSScriptRoot
Set-Location $proyecto
$env:PYTHONUTF8 = "1"                      # acentos y tablas se ven bien en la consola
$env:PYTHONUNBUFFERED = "1"
$exe = Join-Path $proyecto ".venv\Scripts\scalper.exe"
if (-not (Test-Path $exe)) { Write-Host "Falta instalar: ejecuta deploy\instalar-windows.ps1" -ForegroundColor Red; exit 1 }
New-Item -ItemType Directory -Force -Path (Join-Path $proyecto "logs") | Out-Null
$log = Join-Path $proyecto "logs\bot.log"
Write-Host "bot en marcha. Log: $log" -ForegroundColor Green
Write-Host "Deja esta ventana abierta. Ctrl+C detiene el bot guardando los datos." -ForegroundColor Cyan
& $exe -c config.yaml --log-file $log paper
