param(
    [switch]$WithPrecheck,
    [string]$SeedBackupPath = "",
    [switch]$CreateSeedBackup,
    [string]$BrotherDriverInstallerPath = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$version = (Get-Content (Join-Path $projectRoot "VERSION") -Raw).Trim()
$appName = "POSUniformes-$version"
$distDir = Join-Path $projectRoot "dist"
$buildDir = Join-Path $projectRoot "build"
$specPath = Join-Path $projectRoot "packaging\windows\pos_uniformes_windows.spec"
$bundleDir = Join-Path $distDir $appName
$zipPath = Join-Path $distDir "$appName-windows.zip"
$seedDir = Join-Path $projectRoot "packaging\windows\seed"
$bundledSeedPath = Join-Path $seedDir "initial.dump"
$driverDir = Join-Path $projectRoot "packaging\windows\drivers"

if ($CreateSeedBackup -and $SeedBackupPath) {
    throw "Usa solo una opcion: -CreateSeedBackup o -SeedBackupPath."
}

if (-not (Test-Path $venvPython)) {
    py -3.12 -m venv (Join-Path $projectRoot ".venv")
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $projectRoot "requirements.txt") -r (Join-Path $projectRoot "requirements-build.txt")

New-Item -ItemType Directory -Path $seedDir -Force | Out-Null
New-Item -ItemType Directory -Path $driverDir -Force | Out-Null

if (Test-Path $bundledSeedPath) {
    Remove-Item $bundledSeedPath -Force
}

if ($CreateSeedBackup) {
    $generatedSeedDir = Join-Path $projectRoot "packaging\windows\seed\generated"
    if (Test-Path $generatedSeedDir) {
        Remove-Item $generatedSeedDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $generatedSeedDir -Force | Out-Null
    & $venvPython (Join-Path $projectRoot "scripts\backup_database.py") --format custom --output-dir $generatedSeedDir --retention-days 0
    $latestSeed = Get-ChildItem -Path $generatedSeedDir -Filter "*.dump" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latestSeed) {
        throw "No fue posible generar el respaldo semilla."
    }
    Copy-Item $latestSeed.FullName $bundledSeedPath -Force
    Remove-Item $generatedSeedDir -Recurse -Force
}
elseif ($SeedBackupPath) {
    $resolvedSeed = (Resolve-Path $SeedBackupPath).Path
    if (-not $resolvedSeed.EndsWith(".dump")) {
        throw "El respaldo semilla debe ser .dump."
    }
    Copy-Item $resolvedSeed $bundledSeedPath -Force
}

if ($BrotherDriverInstallerPath) {
    $resolvedDriverInstaller = (Resolve-Path $BrotherDriverInstallerPath).Path
    Get-ChildItem -Path $driverDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne ".gitignore" } |
        Remove-Item -Force
    Copy-Item $resolvedDriverInstaller (Join-Path $driverDir ([System.IO.Path]::GetFileName($resolvedDriverInstaller))) -Force
}

if (Test-Path $buildDir) {
    Remove-Item $buildDir -Recurse -Force
}
if (Test-Path $bundleDir) {
    Remove-Item $bundleDir -Recurse -Force
}
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

& $venvPython -m unittest discover -s (Join-Path $projectRoot "tests")
if ($WithPrecheck) {
    & $venvPython (Join-Path $projectRoot "scripts\check_startup_health.py")
}
& $venvPython -m PyInstaller --noconfirm --clean $specPath

Compress-Archive -Path (Join-Path $bundleDir "*") -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "Build lista:"
Write-Host "  Version: $version"
Write-Host "  Carpeta: $bundleDir"
Write-Host "  ZIP:     $zipPath"
if (Test-Path $bundledSeedPath) {
    Write-Host "  Seed:    incluido ($bundledSeedPath)"
}
else {
    Write-Host "  Seed:    no incluido"
}
if (Get-ChildItem -Path $driverDir -File -ErrorAction SilentlyContinue) {
    Write-Host "  Driver:  instalador Brother incluido"
}
else {
    Write-Host "  Driver:  no incluido"
}
Write-Host ""
Write-Host "Antes de ejecutar en otra PC, usa 'setup_windows_local_bundle.ps1' dentro del bundle para dejar la base local lista."
if (-not $WithPrecheck) {
    Write-Host "Nota: el precheck de base se omitio en esta build. Usa -WithPrecheck si quieres validarlo en la maquina de build."
}
