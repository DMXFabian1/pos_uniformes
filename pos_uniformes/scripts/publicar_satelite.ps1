param(
    # Carpeta de la build a publicar. Sin ella, la mas reciente de dist\.
    [string]$BundleDir = ""
)

# Publica la build del kiosko en C:\pos_updates para que cada kiosko la tome
# al abrir. Antes de pisar lo publicado lo guarda en PresupuestosSatelite_anterior:
# de ahi sale "volver a la version anterior" (scripts\volver_version_anterior.bat).
#
# Lo llaman build_presupuestos_satelite_windows.ps1 (cuando publica el mismo) y
# scripts\actualizar.py (que publica DESPUES de migrar la base).

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $BundleDir) {
    $ultima = Get-ChildItem (Join-Path $projectRoot "dist") -Directory -Filter "PresupuestosSatelite-*" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $ultima) {
        Write-Host "*** No hay ninguna build en dist\ para publicar. ***"
        exit 1
    }
    $BundleDir = $ultima.FullName
}
$versionFile = Join-Path $BundleDir "VERSION.txt"
if (-not (Test-Path $versionFile)) {
    Write-Host "*** La build de $BundleDir no trae VERSION.txt: no se publica. ***"
    exit 1
}
$publishedVersion = (Get-Content $versionFile -Raw).Trim()

$updatesDir = $env:POS_UNIFORMES_UPDATES_DIR
if (-not $updatesDir) { $updatesDir = "C:\pos_updates" }
if (-not (Test-Path $updatesDir)) {
    Write-Host "  (No existe $updatesDir - no se publico para kioskos)"
    exit 0
}

$publishDir = Join-Path $updatesDir "PresupuestosSatelite"
$anteriorDir = Join-Path $updatesDir "PresupuestosSatelite_anterior"

# Guardar lo que estaba publicado, si es OTRA version (republicar la misma no
# debe pisar la anterior de verdad con una copia de si misma).
$versionPublicada = ""
$publicadaFile = Join-Path $publishDir "VERSION.txt"
if (Test-Path $publicadaFile) { $versionPublicada = (Get-Content $publicadaFile -Raw).Trim() }
if ($versionPublicada -and ($versionPublicada -ne $publishedVersion)) {
    Write-Host "  Guardando la version anterior ($versionPublicada)..."
    robocopy $publishDir $anteriorDir /MIR /R:2 /W:2 | Out-Null
    if ($LASTEXITCODE -ge 8) {
        Write-Host "  (No se pudo guardar la version anterior - se publica de todas formas)"
    }
}

robocopy $BundleDir $publishDir /MIR /R:2 /W:2 | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Host "*** No se pudo copiar la build a $publishDir (robocopy $LASTEXITCODE). ***"
    exit 1
}
# VERSION.txt lleva fecha + commit: los kioskos se actualizan solos en CADA
# build publicada. Se escribe al final: es lo que les dice "ya hay algo nuevo".
Set-Content -Path (Join-Path $publishDir "VERSION.txt") -Value $publishedVersion
# El lanzador tambien se publica: instalar un kiosko nuevo = copiar
# lanzador_satelite.bat + .ps1 desde la carpeta compartida.
Copy-Item (Join-Path $PSScriptRoot "lanzador_satelite.ps1") $updatesDir -Force
Copy-Item (Join-Path $PSScriptRoot "lanzador_satelite.bat") $updatesDir -Force
# Reparador para el kiosko (cuando el .exe se copia a medias).
Copy-Item (Join-Path $PSScriptRoot "reparar_satelite.bat") $updatesDir -Force -ErrorAction SilentlyContinue
# El instalador del servidor de impresion del kiosko tambien: ahi no hay
# repo ni Python, asi que tiene que llegar por la carpeta compartida.
Copy-Item (Join-Path $PSScriptRoot "instalar_servidor_impresion_kiosko.bat") $updatesDir -Force -ErrorAction SilentlyContinue
Write-Host "  Publicado para kioskos en: $publishDir ($publishedVersion)"
exit 0
