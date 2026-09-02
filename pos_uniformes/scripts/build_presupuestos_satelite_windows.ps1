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

# El bundle lleva un pos_uniformes.env listo junto al exe (copiado del
# .example del repo, la UNICA fuente de estos defaults): una PC satelite
# nueva funciona con solo copiar la carpeta. En la PC servidor se cambia el
# host a localhost o se borra el archivo. Si existe
# %APPDATA%\PresupuestosSatelite\pos_uniformes.env, ese gana sobre este.
Copy-Item (Join-Path $projectRoot "pos_uniformes.env.example") `
    (Join-Path $bundleDir "pos_uniformes.env") -Force

Compress-Archive -Path (Join-Path $bundleDir "*") -DestinationPath $zipPath -Force

# -- Publicacion para kioskos (auto-update por red, sin USB) --------------
# Si existe C:\pos_updates (compartida en red como \\<servidor>\pos_updates),
# la build se copia ahi y el lanzador de cada kiosko se actualiza solo al
# arrancar. Sin la carpeta, este paso simplemente se omite.
$updatesDir = $env:POS_UNIFORMES_UPDATES_DIR
if (-not $updatesDir) { $updatesDir = "C:\pos_updates" }
if (Test-Path $updatesDir) {
    $publishDir = Join-Path $updatesDir "PresupuestosSatelite"
    robocopy $bundleDir $publishDir /MIR /R:2 /W:2 | Out-Null
    Set-Content -Path (Join-Path $publishDir "VERSION.txt") -Value $version
    # El lanzador tambien se publica: instalar un kiosko nuevo = copiar
    # lanzador_satelite.bat + .ps1 desde la carpeta compartida.
    Copy-Item (Join-Path $PSScriptRoot "lanzador_satelite.ps1") $updatesDir -Force
    Copy-Item (Join-Path $PSScriptRoot "lanzador_satelite.bat") $updatesDir -Force
    Write-Host "  Publicado para kioskos en: $publishDir (v$version)"
} else {
    Write-Host "  (No existe $updatesDir - no se publico para kioskos)"
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
