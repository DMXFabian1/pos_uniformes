# Lanzador del satelite con AUTO-ACTUALIZACION por red (sin USB).
#
# Como funciona: al abrirlo, compara la version instalada en este kiosko
# contra la publicada por la PC principal en \\<servidor>\pos_updates.
# Si hay version nueva la copia (la app aun no corre, asi que nada esta
# bloqueado) y arranca el exe local. Si la PC principal esta apagada,
# simplemente arranca la version que ya tiene - nunca deja al kiosko tirado.
#
# Instalacion en un kiosko (UNA sola vez):
#   1. Copiar lanzador_satelite.bat y lanzador_satelite.ps1 desde
#      \\<servidor>\pos_updates a una carpeta local (p.ej. C:\PresupuestosSatelite).
#   2. Crear acceso directo al .bat en el Escritorio (y/o en la carpeta de
#      Inicio para que abra solo al prender la PC).
#   Despues de eso, las actualizaciones llegan solas.

$ErrorActionPreference = "SilentlyContinue"

# El servidor se lee del .env de la app instalada (misma fuente que usa la
# app); 192.168.0.10 solo como default de primera instalacion.
$serverHost = "192.168.0.10"
$appDir = Join-Path $env:LOCALAPPDATA "PresupuestosSatelite\app"
$envFile = Join-Path $appDir "pos_uniformes.env"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*POS_UNIFORMES_SERVER_HOST\s*=\s*(.+)$') {
            $serverHost = $Matches[1].Trim()
        }
    }
}
$share = "\\$serverHost\pos_updates\PresupuestosSatelite"

# Autenticarse al share en CADA arranque: Windows 11 bloquea el acceso como
# invitado y la credencial guardada con /persistent no siempre se reconecta
# a tiempo tras reiniciar. Si ya hay sesion, el error se ignora.
net use "\\$serverHost\pos_updates" pos2026 /user:kiosko /persistent:no 2>$null | Out-Null

function Get-VersionDe($dir) {
    $file = Join-Path $dir "VERSION.txt"
    if (Test-Path $file) { (Get-Content $file -Raw).Trim() } else { "" }
}

$versionLocal = Get-VersionDe $appDir
$versionRemota = ""
if (Test-Path $share) { $versionRemota = Get-VersionDe $share }

if ($versionRemota -and ($versionRemota -ne $versionLocal)) {
    Write-Host "Actualizando satelite: '$versionLocal' -> '$versionRemota' ..."
    Write-Host "(la primera vez copia ~300 MB y tarda unos minutos; se ve avanzar)"
    # /NDL /NP: muestra cada archivo copiado (progreso visible) sin spam.
    robocopy $share $appDir /MIR /R:2 /W:2 /NDL /NP
    Write-Host "Actualizado."
}

# El lanzador tambien se refresca a si mismo desde el share (aplica en el
# SIGUIENTE arranque): instalar mejoras del lanzador ya no requiere USB.
if (Test-Path $share) {
    $updatesRoot = "\\$serverHost\pos_updates"
    foreach ($f in @("lanzador_satelite.ps1", "lanzador_satelite.bat")) {
        Copy-Item (Join-Path $updatesRoot $f) $PSScriptRoot -Force -ErrorAction SilentlyContinue
    }
}

$exe = Get-ChildItem $appDir -Filter "*.exe" -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($exe) {
    Start-Process $exe.FullName -WorkingDirectory $appDir
} else {
    Write-Host ""
    Write-Host "No hay app instalada en este kiosko y no se alcanzo la PC principal."
    Write-Host "Enciende la PC principal (o revisa la red) y vuelve a abrir este acceso."
    Read-Host "Enter para cerrar"
}
