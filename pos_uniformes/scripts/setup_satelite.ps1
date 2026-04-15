<#
.SYNOPSIS
    Deja la PC satelite lista de una sola vez.

.DESCRIPTION
    Este script hace hasta cuatro cosas:
      1. Escribe pos_uniformes.env con la conexion a la PC principal.
      2. Prueba la conexion (avisa si no hay, no bloquea).
      3. Crea un acceso directo en el escritorio.
      4. Opcional (-AutoStart): registra la app para que abra sola al encender la PC.

    Despues de correr este script las empleadas solo necesitan encender la PC.

.EXAMPLE
    # Instalacion tipica con arranque automatico:
    .\setup_satelite.ps1 `
        -TargetDir  "C:\PresupuestosSatelite\PresupuestosSatelite-2026.04.14" `
        -DbHost     "192.168.1.10" `
        -DbPassword "tu_password" `
        -AutoStart

.EXAMPLE
    # Sin arranque automatico:
    .\setup_satelite.ps1 `
        -TargetDir  "C:\PresupuestosSatelite\PresupuestosSatelite-2026.04.14" `
        -DbHost     "192.168.1.10" `
        -DbPassword "tu_password"

.EXAMPLE
    # Solo ver que haria sin ejecutar nada:
    .\setup_satelite.ps1 `
        -TargetDir  "C:\PresupuestosSatelite\PresupuestosSatelite-2026.04.14" `
        -DbHost     "192.168.1.10" `
        -DbPassword "tu_password" `
        -AutoStart `
        -DryRun

.EXAMPLE
    # Quitar el arranque automatico:
    .\setup_satelite.ps1 `
        -TargetDir  "C:\PresupuestosSatelite\PresupuestosSatelite-2026.04.14" `
        -DbHost     "192.168.1.10" `
        -DbPassword "tu_password" `
        -RemoveAutoStart
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$TargetDir,

    [Parameter(Mandatory = $true)]
    [string]$DbHost,

    [string]$DbPort      = "5432",
    [string]$DbName      = "pos_uniformes",
    [string]$DbUser      = "postgres",

    [Parameter(Mandatory = $true)]
    [string]$DbPassword,

    [string]$ShortcutName = "Presupuestos Satelite",

    # Registra la app para que abra automaticamente al iniciar sesion en Windows.
    # Usa la carpeta Startup del usuario — no requiere permisos de administrador.
    # Se agrega un retraso de 15 segundos para que la red este lista primero.
    [switch]$AutoStart,

    # Quita el arranque automatico si ya estaba configurado.
    [switch]$RemoveAutoStart,

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

$startupFolder = [Environment]::GetFolderPath("Startup")
$startupShortcut = Join-Path $startupFolder "$ShortcutName.lnk"

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
# Paso 1 — Escribir pos_uniformes.env en AppData (persiste entre updates)
# ---------------------------------------------------------------------------

Write-Step "Paso 1 — Configurar pos_uniformes.env"

$appDataDir = Join-Path $env:APPDATA "PresupuestosSatelite"
$envFile    = Join-Path $appDataDir "pos_uniformes.env"
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
    Write-Dry "Crearia carpeta: $appDataDir"
    Write-Dry "Escribiria $envFile con DbHost=$DbHost, DbUser=$DbUser, DbName=$DbName"
} else {
    if (-not (Test-Path $appDataDir)) {
        New-Item -ItemType Directory -Path $appDataDir -Force | Out-Null
    }
    Set-Content -Path $envFile -Value $envContent -Encoding ascii
    Write-Ok "ENV escrito: $envFile"
    Write-Host "  (La configuracion persiste automaticamente entre updates del bundle)" -ForegroundColor DarkGray
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

$desktopPath  = [Environment]::GetFolderPath("Desktop")
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
# Paso 4 — Arranque automatico (opcional)
# ---------------------------------------------------------------------------

if ($RemoveAutoStart) {
    Write-Step "Paso 4 — Quitar arranque automatico"
    if ($DryRun) {
        Write-Dry "Eliminaria $startupShortcut si existe"
    } elseif (Test-Path $startupShortcut) {
        Remove-Item $startupShortcut -Force
        Write-Ok "Arranque automatico eliminado: $startupShortcut"
    } else {
        Write-Ok "No habia arranque automatico configurado."
    }
} elseif ($AutoStart) {
    Write-Step "Paso 4 — Configurar arranque automatico al iniciar sesion"
    Write-Host "  Metodo: carpeta Startup del usuario (no requiere administrador)" -ForegroundColor DarkGray
    Write-Host "  Retraso: 15 segundos para que la red este lista primero" -ForegroundColor DarkGray

    if ($DryRun) {
        Write-Dry "Crearia acceso directo en Startup: $startupShortcut"
        Write-Dry "Con retraso de 15s via wrapper VBScript"
    } else {
        # Crear un VBScript que espera 15s y luego lanza el exe.
        # El retraso es importante: si la app arranca antes de que
        # Windows conecte a la red, el probe TCP falla y abre en modo
        # offline aunque la PC principal este encendida.
        $wrapperPath = Join-Path $TargetDir "iniciar_satelite.vbs"
        $wrapperContent = @"
WScript.Sleep 15000
Set oShell = CreateObject("WScript.Shell")
oShell.Run """$($exe.FullName)""", 1, False
"@
        Set-Content -Path $wrapperPath -Value $wrapperContent -Encoding ascii

        $shell2   = New-Object -ComObject WScript.Shell
        $shortcut2 = $shell2.CreateShortcut($startupShortcut)
        $shortcut2.TargetPath       = "wscript.exe"
        $shortcut2.Arguments        = """$wrapperPath"""
        $shortcut2.WorkingDirectory = $TargetDir
        $shortcut2.Description      = "Presupuestos Satelite — arranque automatico"
        $shortcut2.Save()

        Write-Ok "Arranque automatico configurado: $startupShortcut"
        Write-Ok "Wrapper creado: $wrapperPath"
    }
} else {
    Write-Step "Paso 4 — Arranque automatico"
    Write-Host "  Omitido. Usa -AutoStart para configurarlo." -ForegroundColor DarkGray
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
    if ($AutoStart) {
        Write-Host "  La app abrira sola 15 segundos despues de que la empleada inicie sesion." -ForegroundColor White
    } else {
        Write-Host "  La empleada solo necesita hacer doble clic en:" -ForegroundColor White
        Write-Host "    $shortcutPath" -ForegroundColor White
    }
    Write-Host ""
    Write-Host "  Si la PC principal esta encendida: abre normal." -ForegroundColor DarkGray
    Write-Host "  Si la PC principal esta apagada:   abre con catalogo guardado." -ForegroundColor DarkGray
}
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host ""
