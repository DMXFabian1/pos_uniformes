# Instalación del bot en Windows 10/11. Se puede repetir para actualizar.
# Uso, desde PowerShell y dentro de la carpeta del proyecto:
#   powershell -ExecutionPolicy Bypass -File deploy\instalar-windows.ps1
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }   # acentos legibles en PowerShell 5.1
$proyecto = Split-Path -Parent $PSScriptRoot
Set-Location $proyecto

Write-Host "== buscando Python" -ForegroundColor Cyan
$py = $null
foreach ($cand in @(@("py", @("-3")), @("python", @()), @("python3", @()))) {
  $nombre = $cand[0]; $pre = $cand[1]
  if (-not (Get-Command $nombre -ErrorAction SilentlyContinue)) { continue }
  try { $v = & $nombre @($pre + @("--version")) 2>&1 } catch { continue }
  if ("$v" -match "Python 3\.(\d+)") {
    if ([int]$Matches[1] -ge 11) { $py = @($nombre, $pre); Write-Host "   $v"; break }
    Write-Host "   $v es muy antigua; hace falta 3.11 o superior" -ForegroundColor Yellow
  }
}
if (-not $py) {
  Write-Host "No encontré Python 3.11+. Instálalo desde https://www.python.org/downloads/ " -ForegroundColor Red
  Write-Host "y marca 'Add python.exe to PATH' durante la instalación. Luego vuelve a ejecutar este script." -ForegroundColor Red
  exit 1
}

Write-Host "== entorno virtual .venv" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) { & $py[0] @($py[1] + @("-m", "venv", ".venv")) }
# en Windows pip.exe no puede reemplazarse a sí mismo: siempre se invoca como "python -m pip"
$vpy = Join-Path $proyecto ".venv\Scripts\python.exe"
$exe = Join-Path $proyecto ".venv\Scripts\scalper.exe"
if (-not (Test-Path $vpy)) { Write-Host "no se creó el entorno virtual .venv" -ForegroundColor Red; exit 1 }

# restos de instalaciones interrumpidas: pip avisa de "invalid distribution ~..." en cada uso
$sitePkgs = Join-Path $proyecto ".venv\Lib\site-packages"
if (Test-Path $sitePkgs) {
  Get-ChildItem -Path $sitePkgs -Directory -Filter "~*" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "   limpiando resto: $($_.Name)" -ForegroundColor DarkGray
    Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
  }
}

Write-Host "== dependencias (puede tardar unos minutos)" -ForegroundColor Cyan
& $vpy -m pip install --quiet --upgrade pip
& $vpy -m pip install --quiet -e ".[learn,gui]"
if ($LASTEXITCODE -ne 0) {
  Write-Host "falló la instalación de dependencias" -ForegroundColor Red
  Write-Host "prueba a mano para ver el detalle:" -ForegroundColor Yellow
  Write-Host "  $vpy -m pip install -e `".[learn]`"" -ForegroundColor Yellow
  exit 1
}

Write-Host "== comprobación" -ForegroundColor Cyan
$env:PYTHONUTF8 = "1"
& $exe --help | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "el comando scalper no responde" -ForegroundColor Red; exit 1 }
New-Item -ItemType Directory -Force -Path (Join-Path $proyecto "data") | Out-Null

Write-Host ""
Write-Host "Listo. Desde esta carpeta:" -ForegroundColor Green
Write-Host "  SCALPER.bat                     abre la aplicacion con ventana y botones"
Write-Host "  .\deploy\iniciar-bot.ps1        arranca el bot (paper trading, sin dinero real)"
Write-Host "  .\deploy\iniciar-panel.ps1      abre el panel en http://127.0.0.1:8787"
Write-Host "  .\deploy\programar-inicio.ps1   para que el bot arranque solo al encender la PC"
Write-Host ""
Write-Host "Comandos sueltos: .venv\Scripts\scalper.exe status | report | wallets | retention"
