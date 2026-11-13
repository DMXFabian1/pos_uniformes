param(
    [switch]$WithPrecheck,
    # Solo construir: la publicacion la hace el actualizador DESPUES de migrar
    # (scripts\actualizar.py). Asi un build que falla no deja la base cambiada.
    [switch]$SinPublicar
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$version = (Get-Content (Join-Path $projectRoot "VERSION") -Raw).Trim()
$appName = "PresupuestosSatelite-$version"
$distDir = Join-Path $projectRoot "dist"
$buildDir = Join-Path $projectRoot "build"
$specPath = Join-Path $projectRoot "packaging\windows\presupuestos_satelite_windows.spec"
$bundleDir = Join-Path $distDir $appName
$zipPath = Join-Path $distDir "$appName-windows.zip"

if (-not (Test-Path $venvPython)) {
    py -3.12 -m venv (Join-Path $projectRoot ".venv")
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $projectRoot "requirements.txt") -r (Join-Path $projectRoot "requirements-build.txt")

if (Test-Path $buildDir) {
    Remove-Item $buildDir -Recurse -Force
}
if (Test-Path $bundleDir) {
    Remove-Item $bundleDir -Recurse -Force
}
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

& $venvPython -m unittest `
    tests.test_quote_action_service `
    tests.test_quote_catalog_browser_helper `
    tests.test_quote_cart_view_helper `
    tests.test_quote_detail_helper `
    tests.test_quote_editor_service `
    tests.test_quote_feedback_helper `
    tests.test_quote_kiosk_lookup_helper `
    tests.test_quote_satellite_filter_helper `
    tests.test_quote_snapshot_service `
    tests.test_quote_text_service `
    tests.test_quote_whatsapp_service `
    tests.test_catalog_local_cache_service `
    tests.test_satellite_startup_service
if ($WithPrecheck) {
    & $venvPython (Join-Path $projectRoot "scripts\check_startup_health.py")
}
& $venvPython -m PyInstaller --noconfirm --clean $specPath
# Si PyInstaller no termino bien, hasta aqui: sin esto el script seguia y el
# actualizador creia que habia build (y migraba la base para un programa que no existe).
if ($LASTEXITCODE -ne 0) {
    Write-Host "*** PyInstaller fallo (codigo $LASTEXITCODE): no hay build. ***"
    exit 1
}

# El bundle lleva un pos_uniformes.env listo junto al exe (copiado del
# .example del repo, la UNICA fuente de estos defaults): una PC satelite
# nueva funciona con solo copiar la carpeta. En la PC servidor se cambia el
# host a localhost o se borra el archivo. Si existe
# %APPDATA%\PresupuestosSatelite\pos_uniformes.env, ese gana sobre este.
Copy-Item (Join-Path $projectRoot "pos_uniformes.env.example") `
    (Join-Path $bundleDir "pos_uniformes.env") -Force

# VERSION.txt (version+commit) va DENTRO del bundle: la app lo lee como su
# version instalada y lo compara contra el publicado en el share. Si la build
# no lo trajera, la app compararia "2026.11.11" contra "2026.11.11+abc123" y
# avisaria de una actualizacion que ya tiene, en cada arranque.
$commit = ""
try { $commit = (& git -C $projectRoot rev-parse --short HEAD 2>$null).Trim() } catch {}
# Lo publicado es FECHA DEL ULTIMO CAMBIO + commit (2026.11.06+6ba73b01), no
# el archivo VERSION: ese se subia a mano y se quedo quieto. La app lo ensena
# como "Version 6 nov - 6ba73b01". Sin git, cae al VERSION de siempre.
$fecha = ""
try { $fecha = (& git -C $projectRoot log -1 --format=%cd --date=format:%Y.%m.%d 2>$null).Trim() } catch {}
if (-not $fecha) { $fecha = $version }
$publishedVersion = if ($commit) { "$fecha+$commit" } else { $version }
Set-Content -Path (Join-Path $bundleDir "VERSION.txt") -Value $publishedVersion

Compress-Archive -Path (Join-Path $bundleDir "*") -DestinationPath $zipPath -Force

# -- Publicacion para kioskos (auto-update por red, sin USB) --------------
# Vive en publicar_satelite.ps1: guarda la version anterior y luego copia la
# nueva a C:\pos_updates. Con -SinPublicar se deja para despues.
if ($SinPublicar) {
    Write-Host "  (Build lista SIN publicar: se publica despues de migrar la base)"
} else {
    & (Join-Path $PSScriptRoot "publicar_satelite.ps1") -BundleDir $bundleDir
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

Write-Host ""
Write-Host "Build satelite lista:"
Write-Host "  Version: $version"
Write-Host "  Carpeta: $bundleDir"
Write-Host "  ZIP:     $zipPath"
Write-Host ""
Write-Host "El bundle ya incluye pos_uniformes.env (copiado del .example, apunta al servidor) - una PC satelite nueva funciona con solo copiar la carpeta."
if (-not $WithPrecheck) {
    Write-Host "Nota: el precheck de base se omitio en esta build. Usa -WithPrecheck si quieres validarlo."
}
