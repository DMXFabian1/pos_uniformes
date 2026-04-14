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
$bundleInternalDir = Join-Path $bundleDir "_internal"
$zipPath = Join-Path $distDir "$appName-windows.zip"
$seedDir = Join-Path $projectRoot "packaging\windows\seed"
$bundledSeedPath = Join-Path $seedDir "initial.dump"
$driverDir = Join-Path $projectRoot "packaging\windows\drivers"
$repoRoot = Split-Path $projectRoot -Parent

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "El comando fallo ($LASTEXITCODE): $FilePath $($Arguments -join ' ')"
    }
}

function Sync-BundleSupportFiles {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BundleDir,
        [Parameter(Mandatory = $true)]
        [string]$BundleInternalDir
    )

    $rootFiles = @(
        "pos_uniformes.env.example",
        "setup_windows_local_bundle.ps1",
        "setup_windows_local_bundle.bat",
        "VERSION"
    )

    foreach ($fileName in $rootFiles) {
        $sourcePath = Join-Path $BundleInternalDir $fileName
        if (Test-Path $sourcePath) {
            Copy-Item $sourcePath (Join-Path $BundleDir $fileName) -Force
        }
    }

    foreach ($directoryName in @("seed", "drivers")) {
        $sourceDir = Join-Path $BundleInternalDir $directoryName
        $targetDir = Join-Path $BundleDir $directoryName
        if (-not (Test-Path $sourceDir)) {
            continue
        }
        if (Test-Path $targetDir) {
            Remove-Item $targetDir -Recurse -Force
        }
        Copy-Item $sourceDir $targetDir -Recurse -Force
    }
}

if ($CreateSeedBackup -and $SeedBackupPath) {
    throw "Usa solo una opcion: -CreateSeedBackup o -SeedBackupPath."
}

if (-not (Test-Path $venvPython)) {
    py -3.12 -m venv (Join-Path $projectRoot ".venv")
}

Invoke-NativeCommand $venvPython -m pip install --upgrade pip
Invoke-NativeCommand $venvPython -m pip install -r (Join-Path $projectRoot "requirements.txt") -r (Join-Path $projectRoot "requirements-build.txt")

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
    Invoke-NativeCommand $venvPython (Join-Path $projectRoot "scripts\backup_database.py") --format custom --output-dir $generatedSeedDir --retention-days 0
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

Push-Location $repoRoot
try {
    Invoke-NativeCommand $venvPython -m unittest discover -s (Join-Path $projectRoot "tests") -t $repoRoot
}
finally {
    Pop-Location
}
if ($WithPrecheck) {
    Invoke-NativeCommand $venvPython (Join-Path $projectRoot "scripts\check_startup_health.py")
}
Invoke-NativeCommand $venvPython -m PyInstaller --noconfirm --clean $specPath

Sync-BundleSupportFiles -BundleDir $bundleDir -BundleInternalDir $bundleInternalDir

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
