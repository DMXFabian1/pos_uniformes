param(
    [string]$DbHost = "localhost",
    [string]$DbPort = "5432",
    [string]$DbName = "pos_uniformes",
    [string]$DbUser = "postgres",
    [string]$DbPassword = "postgres",
    [string]$AdminUser = "",
    [string]$AdminPassword = "",
    [switch]$AllowEmptySchema
)

$ErrorActionPreference = "Stop"

function Resolve-PostgresBinary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BinaryName
    )

    $direct = Get-Command $BinaryName -ErrorAction SilentlyContinue
    if ($direct) {
        return $direct.Source
    }

    $roots = @(
        "C:\Program Files\PostgreSQL",
        "C:\Program Files (x86)\PostgreSQL"
    )
    foreach ($root in $roots) {
        if (-not (Test-Path $root)) {
            continue
        }
        $matches = Get-ChildItem -Path $root -Directory | Sort-Object Name -Descending
        foreach ($match in $matches) {
            $candidate = Join-Path $match.FullName "bin\$BinaryName"
            if (Test-Path $candidate) {
                return $candidate
            }
        }
    }

    throw "No se encontro '$BinaryName'. Instala PostgreSQL y agrega su carpeta bin al PATH."
}

function Invoke-PostgresCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Password,
        [Parameter(Mandatory = $true)]
        [string[]]$Command
    )

    $previousPassword = $env:PGPASSWORD
    try {
        $env:PGPASSWORD = $Password
        $commandHead = $Command[0]
        $commandTail = @()
        if ($Command.Length -gt 1) {
            $commandTail = $Command[1..($Command.Length - 1)]
        }
        & $commandHead $commandTail
        if ($LASTEXITCODE -ne 0) {
            throw "El comando PostgreSQL fallo con codigo $LASTEXITCODE."
        }
    }
    finally {
        $env:PGPASSWORD = $previousPassword
    }
}

function Write-EnvFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TemplatePath,
        [Parameter(Mandatory = $true)]
        [string]$OutputPath
    )

    $content = Get-Content $TemplatePath -Raw
    $content = [regex]::Replace($content, '^POS_UNIFORMES_DB_HOST=.*$', "POS_UNIFORMES_DB_HOST=$DbHost", 'Multiline')
    $content = [regex]::Replace($content, '^POS_UNIFORMES_DB_PORT=.*$', "POS_UNIFORMES_DB_PORT=$DbPort", 'Multiline')
    $content = [regex]::Replace($content, '^POS_UNIFORMES_DB_NAME=.*$', "POS_UNIFORMES_DB_NAME=$DbName", 'Multiline')
    $content = [regex]::Replace($content, '^POS_UNIFORMES_DB_USER=.*$', "POS_UNIFORMES_DB_USER=$DbUser", 'Multiline')
    $content = [regex]::Replace($content, '^POS_UNIFORMES_DB_PASSWORD=.*$', "POS_UNIFORMES_DB_PASSWORD=$DbPassword", 'Multiline')
    $content = [regex]::Replace($content, '^POS_UNIFORMES_AUTO_CREATE_SCHEMA=.*$', "POS_UNIFORMES_AUTO_CREATE_SCHEMA=0", 'Multiline')
    Set-Content -Path $OutputPath -Value $content -Encoding UTF8
}

$bundleDir = $PSScriptRoot
$seedBackup = Join-Path $bundleDir "seed\initial.dump"
$envTemplatePath = Join-Path $bundleDir "pos_uniformes.env.example"
$envOutputPath = Join-Path $bundleDir "pos_uniformes.env"
$exePath = Get-ChildItem -Path $bundleDir -Filter "POSUniformes-*.exe" | Select-Object -First 1

if (-not $AdminUser) {
    $AdminUser = $DbUser
}
if (-not $AdminPassword) {
    $AdminPassword = $DbPassword
}

$psql = Resolve-PostgresBinary -BinaryName "psql.exe"
$createdb = Resolve-PostgresBinary -BinaryName "createdb.exe"
$pgRestore = Resolve-PostgresBinary -BinaryName "pg_restore.exe"

$existsCheckCommand = @(
    $psql,
    "--host", $DbHost,
    "--port", $DbPort,
    "--username", $AdminUser,
    "--dbname", "postgres",
    "--tuples-only",
    "--no-align",
    "--command", "SELECT 1 FROM pg_database WHERE datname = '$DbName';"
)

$previousPassword = $env:PGPASSWORD
try {
    $env:PGPASSWORD = $AdminPassword
    $existsCheckHead = $existsCheckCommand[0]
    $existsCheckTail = $existsCheckCommand[1..($existsCheckCommand.Length - 1)]
    $databaseExists = (& $existsCheckHead $existsCheckTail | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "No fue posible consultar si la base '$DbName' existe."
    }
}
finally {
    $env:PGPASSWORD = $previousPassword
}

if (-not $databaseExists) {
    Invoke-PostgresCommand -Password $AdminPassword -Command @(
        $createdb,
        "--host", $DbHost,
        "--port", $DbPort,
        "--username", $AdminUser,
        "--owner", $DbUser,
        $DbName
    )
}

if (Test-Path $seedBackup) {
    Invoke-PostgresCommand -Password $DbPassword -Command @(
        $pgRestore,
        "--host", $DbHost,
        "--port", $DbPort,
        "--username", $DbUser,
        "--dbname", $DbName,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--verbose",
        $seedBackup
    )
}
elseif (-not $AllowEmptySchema) {
    throw "Este bundle no incluye un respaldo semilla en 'seed\\initial.dump'. Usa -AllowEmptySchema si solo quieres dejar el env listo."
}

Write-EnvFile -TemplatePath $envTemplatePath -OutputPath $envOutputPath

Write-Host ""
Write-Host "Setup local completado:"
Write-Host "  Host:   $DbHost"
Write-Host "  Puerto: $DbPort"
Write-Host "  Base:   $DbName"
Write-Host "  Usuario:$DbUser"
Write-Host "  ENV:    $envOutputPath"
if (Test-Path $seedBackup) {
    Write-Host "  Seed:   $seedBackup"
}
elseif ($AllowEmptySchema) {
    Write-Host "  Seed:   no incluido; solo se preparo la conexion"
}
if ($exePath) {
    Write-Host "  EXE:    $($exePath.FullName)"
}
Write-Host ""
Write-Host "Siguiente paso: abre el ejecutable desde esta misma carpeta."
