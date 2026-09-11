# Registra el bot y el panel como tareas de Windows: arrancan al iniciar sesión y se reinician solos.
# Ejecutar como administrador:
#   powershell -ExecutionPolicy Bypass -File deploy\programar-inicio.ps1
# Para quitarlas:  deploy\programar-inicio.ps1 -Quitar
param([switch]$Quitar)
$ErrorActionPreference = "Stop"
$proyecto = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $proyecto ".venv\Scripts\scalper.exe"
$tareas = @(
  @{ Nombre = "ScalperPolymarket-Bot";   Args = "-c `"$proyecto\config.yaml`" --log-file `"$proyecto\logs\bot.log`" paper" },
  @{ Nombre = "ScalperPolymarket-Panel"; Args = "-c `"$proyecto\config.yaml`" --log-file `"$proyecto\logs\panel.log`" dashboard" }
)

if ($Quitar) {
  foreach ($t in $tareas) { Unregister-ScheduledTask -TaskName $t.Nombre -Confirm:$false -ErrorAction SilentlyContinue }
  Write-Host "tareas eliminadas" -ForegroundColor Green
  exit 0
}
if (-not (Test-Path $exe)) { Write-Host "Falta instalar: ejecuta deploy\instalar-windows.ps1" -ForegroundColor Red; exit 1 }
New-Item -ItemType Directory -Force -Path (Join-Path $proyecto "logs") | Out-Null

foreach ($t in $tareas) {
  $accion = New-ScheduledTaskAction -Execute $exe -Argument $t.Args -WorkingDirectory $proyecto
  $disparador = New-ScheduledTaskTrigger -AtLogOn
  $opciones = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
      -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
      -MultipleInstances IgnoreNew -StartWhenAvailable
  Register-ScheduledTask -TaskName $t.Nombre -Action $accion -Trigger $disparador -Settings $opciones `
      -Description "Bot de scalping para Polymarket (paper trading, sin dinero real)" -Force | Out-Null
  Write-Host "tarea registrada: $($t.Nombre)" -ForegroundColor Green
}
Write-Host ""
Write-Host "Arrancan solas al iniciar sesión en Windows. Para verlas: Programador de tareas."
Write-Host "Arrancar ahora sin reiniciar:  Start-ScheduledTask -TaskName ScalperPolymarket-Bot"
Write-Host "Ver estado:                    Get-ScheduledTask -TaskName ScalperPolymarket-*"
