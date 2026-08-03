param(
    [switch]$WithPrecheck
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
    tests.test_quote_selection_helper `
    tests.test_quote_snapshot_service `
    tests.test_quote_text_service `
    tests.test_quote_whatsapp_service `
    tests.test_catalog_local_cache_service `
    tests.test_satellite_startup_service
if ($WithPrecheck) {
    & $venvPython (Join-Path $projectRoot "scripts\check_startup_health.py")
}
& $venvPython -m PyInstaller --noconfirm --clean $specPath

# Genera un pos_uniformes.env listo junto al exe: una PC satelite nueva
# funciona con solo copiar la carpeta, sin configurar nada a mano.
$envContent = @"
# Configuracion de base de datos — la app lee este archivo al arrancar.
#
# PC SATELITE (caso normal de este archivo): la base vive en la PC principal.
#   Deja POS_UNIFORMES_DB_HOST con la IP del servidor. No hay que hacer nada mas.
#
# PC PRINCIPAL/SERVIDOR (donde corre PostgreSQL): cambia el host a localhost,
#   o borra este archivo (localhost es el default sin archivo).
#
# Si existe %APPDATA%\PresupuestosSatelite\pos_uniformes.env, ese gana sobre este.
POS_UNIFORMES_DB_HOST=192.168.0.10
POS_UNIFORMES_DB_PORT=5432
POS_UNIFORMES_DB_NAME=pos_uniformes
POS_UNIFORMES_DB_USER=postgres
POS_UNIFORMES_DB_PASSWORD=1234
POS_UNIFORMES_DB_ECHO=0
POS_UNIFORMES_AUTO_CREATE_SCHEMA=0
"@
[System.IO.File]::WriteAllText(
    (Join-Path $bundleDir "pos_uniformes.env"),
    $envContent,
    (New-Object System.Text.UTF8Encoding($false))
)

Compress-Archive -Path (Join-Path $bundleDir "*") -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "Build satelite lista:"
Write-Host "  Version: $version"
Write-Host "  Carpeta: $bundleDir"
Write-Host "  ZIP:     $zipPath"
Write-Host ""
Write-Host "El bundle ya incluye pos_uniformes.env apuntando al servidor (192.168.0.10) — una PC satelite nueva funciona con solo copiar la carpeta."
if (-not $WithPrecheck) {
    Write-Host "Nota: el precheck de base se omitio en esta build. Usa -WithPrecheck si quieres validarlo."
}
