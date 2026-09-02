# Lanzador del satélite con AUTO-ACTUALIZACIÓN por red (sin USB).
#
# Cómo funciona: al abrirlo, compara la versión instalada en este kiosko
# contra la publicada por la PC principal en \\<servidor>\pos_updates.
# Si hay versión nueva la copia (la app aún no corre, así que nada está
# bloqueado) y arranca el exe local. Si la PC principal está apagada,
# simplemente arranca la versión que ya tiene — nunca deja al kiosko tirado.
#
# Instalación en un kiosko (UNA sola vez):
#   1. Copiar lanzador_satelite.bat y lanzador_satelite.ps1 desde
#      \\<servidor>\pos_updates a una carpeta local (p.ej. C:\PresupuestosSatelite).
#   2. Crear acceso directo al .bat en el Escritorio (y/o en la carpeta de
#      Inicio para que abra solo al prender la PC).
#   Después de eso, las actualizaciones llegan solas.

$ErrorActionPreference = "SilentlyContinue"

# El servidor se lee del .env de la app instalada (misma fuente que usa la
# app); 192.168.0.10 solo como default de primera instalación.
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

function Get-VersionDe($dir) {
    $file = Join-Path $dir "VERSION.txt"
    if (Test-Path $file) { (Get-Content $file -Raw).Trim() } else { "" }
}

$versionLocal = Get-VersionDe $appDir
$versionRemota = ""
if (Test-Path $share) { $versionRemota = Get-VersionDe $share }

if ($versionRemota -and ($versionRemota -ne $versionLocal)) {
    Write-Host "Actualizando satelite: '$versionLocal' -> '$versionRemota' ..."
    robocopy $share $appDir /MIR /R:2 /W:2 | Out-Null
    Write-Host "Actualizado."
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
