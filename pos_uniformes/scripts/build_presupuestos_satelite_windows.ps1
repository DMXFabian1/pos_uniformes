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
    tests.test_quote_whatsapp_service
if ($WithPrecheck) {
    & $venvPython (Join-Path $projectRoot "scripts\check_startup_health.py")
}
& $venvPython -m PyInstaller --noconfirm --clean $specPath

Compress-Archive -Path (Join-Path $bundleDir "*") -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "Build satelite lista:"
Write-Host "  Version: $version"
Write-Host "  Carpeta: $bundleDir"
Write-Host "  ZIP:     $zipPath"
Write-Host ""
Write-Host "Configura el .env de la PC satelite para apuntar a la misma base PostgreSQL del sistema principal."
if (-not $WithPrecheck) {
    Write-Host "Nota: el precheck de base se omitio en esta build. Usa -WithPrecheck si quieres validarlo."
}
