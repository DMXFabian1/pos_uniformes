<#
.SYNOPSIS
    Deja la PC satelite lista de una sola vez.

.DESCRIPTION
    Este script hace tres cosas:
      1. Escribe pos_uniformes.env con la conexion a la PC principal.
      2. Prueba la conexion (avisa si no hay, no bloquea).
      3. Crea un acceso directo en el escritorio.

    Despues de correr este script las empleadas solo necesitan hacer doble
    clic en el acceso directo del escritorio.

.EXAMPLE
    # Instalacion tipica:
    .\setup_satelite.ps1 `
        -TargetDir "C:\PresupuestosSatelite\PresupuestosSatelite-2026.04.14" `
        -DbHost    "192.168.1.10" `
        -DbPassword "tu_password"

.EXAMPLE
    # Si el usuario de postgres no es el default:
    .\setup_satelite.ps1 `
        -TargetDir  "C:\PresupuestosSatelite\PresupuestosSatelite-2026.04.14" `
        -DbHost     "192.168.1.10" `
        -DbUser     "pos_app" `
        -DbPassword "tu_password" `
        -DbName     "pos_uniformes"

.EXAMPLE
    # Solo ver que haria sin ejecutar nada:
    .\setup_satelite.ps1 `
        -TargetDir  "C:\PresupuestosSatelite\PresupuestosSatelite-2026.04.14" `
        -DbHost     "192.168.1.10" `
        -DbPassword "tu_password" `
        -DryRun
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$TargetDir,

    [Parameter(Mandatory = $true)]
    [string]$DbHost,

    [string]$DbPort     = "5432",
    [string]$DbName     = "pos_uniformes",
    [string]$DbUser     = "postgres",

    [Parameter(Mandatory = $true)]
    [string]$DbPassword,

    [string]$ShortcutName = "Presupuestos Satelite",

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host $msg -ForegroundColor Cyan
}

function Write-Ok([string]$msg) {
    Write-Host "  OK  $msg" -ForegroundColor Green
}

function Write-Warn([string]$msg) {
    Write-Host "  AVISO  $msg" -ForegroundColor Yellow
}

function Write-Dry([string]$msg) {
    Write-Host "  [dry-run]  $msg" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# Validacion inicial
# ---------------------------------------------------------------------------

Write-Step "Verificando carpeta del satelite"

$TargetDir = (Resolve-Path $TargetDir -ErrorAction Stop).Path

if (-not (Test-Path $TargetDir)) {
    throw "No existe la carpeta: $TargetDir"
}

$exe = Get-ChildItem $TargetDir -Filter "*.exe" -File | Select-Object -First 1
if (-not $exe) {
    throw "No encontre ningun .exe en $TargetDir. Descomprime el bundle primero."
}

Write-Ok "Carpeta: $TargetDir"
Write-Ok "Ejecutable: $($exe.Name)"

# ---------------------------------------------------------------------------
# Paso 1 — Escribir pos_uniformes.env
# ---------------------------------------------------------------------------

Write-Step "Paso 1 — Configurar pos_uniformes.env"

$envFile = Join-Path $TargetDir "pos_uniformes.env"
$envContent = @"
POS_UNIFORMES_DB_HOST=$DbHost
POS_UNIFORMES_DB_PORT=$DbPort
POS_UNIFORMES_DB_NAME=$DbName
POS_UNIFORMES_DB_USER=$DbUser
POS_UNIFORMES_DB_PASSWORD=$DbPassword
POS_UNIFORMES_DB_ECHO=0
POS_UNIFORMES_AUTO_CREATE_SCHEMA=0
POS_UNIFORMES_BACKUP_EXTERNAL_DIR=
"@

if ($DryRun) {
    Write-Dry "Escribiria $envFile con DbHost=$DbHost, DbUser=$DbUser, DbName=$DbName"
} else {
    Set-Content -Path $envFile -Value $envContent -Encoding ascii
    Write-Ok "ENV escrito: $envFile"
}

# ---------------------------------------------------------------------------
# Paso 2 — Probar conexion (no bloquea)
# ---------------------------------------------------------------------------

Write-Step "Paso 2 — Probar conexion con la PC principal ($DbHost`:$DbPort)"

if ($DryRun) {
    Write-Dry "Saltando prueba de conexion en dry-run"
} else {
    $connection = Test-NetConnection $DbHost -Port ([int]$DbPort) -WarningAction SilentlyContinue
    if ($connection.TcpTestSucceeded) {
        Write-Ok "Conexion exitosa hacia $DbHost`:$DbPort"
    } else {
        Write-Warn "No se pudo conectar con $DbHost`:$DbPort ahora."
        Write-Warn "La app abrira en modo local la proxima vez que no haya conexion."
        Write-Warn "Para el primer uso real enciende la PC principal para generar el catalogo guardado."
    }
}

# ---------------------------------------------------------------------------
# Paso 3 — Crear acceso directo en el escritorio
# ---------------------------------------------------------------------------

Write-Step "Paso 3 — Crear acceso directo en el escritorio"

$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "$ShortcutName.lnk"

if ($DryRun) {
    Write-Dry "Crearia acceso directo: $shortcutPath -> $($exe.FullName)"
} else {
    $shell    = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath       = $exe.FullName
    $shortcut.WorkingDirectory = $TargetDir
    $shortcut.IconLocation     = $exe.FullName
    $shortcut.Description      = "Presupuestos Satelite — POS Uniformes"
    $shortcut.Save()
    Write-Ok "Acceso directo creado: $shortcutPath"
}

# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
if ($DryRun) {
    Write-Host "  Dry-run completado. No se escribio ni creo nada." -ForegroundColor DarkGray
} else {
    Write-Host "  Satelite listo." -ForegroundColor Green
    Write-Host ""
    Write-Host "  La empleada solo necesita hacer doble clic en:" -ForegroundColor White
    Write-Host "    $shortcutPath" -ForegroundColor White
    Write-Host ""
    Write-Host "  Si la PC principal esta encendida: abre normal." -ForegroundColor DarkGray
    Write-Host "  Si la PC principal esta apagada:   abre con catalogo guardado." -ForegroundColor DarkGray
}
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host ""
