#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Habilita conexiones remotas en PostgreSQL y abre el puerto 5432 en el firewall.
    Ejecutar como Administrador en la PC Windows (la que tiene la base de datos).
#>

param(
    [string]$PgPort = "5432"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step { param($msg) Write-Host "`n== $msg ==" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  !!  $msg" -ForegroundColor Yellow }

# ── 1. Localizar directorio de datos de PostgreSQL ───────────────────────────
Write-Step "Buscando directorio de datos de PostgreSQL"

$dataDir = $null

# Intentar via psql
try {
    $rawPath = & psql -U postgres -t -c "SHOW data_directory;" 2>$null
    if ($rawPath) { $dataDir = $rawPath.Trim() }
} catch {}

# Fallback: buscar en rutas típicas
if (-not $dataDir -or -not (Test-Path $dataDir)) {
    $candidates = @(
        "C:\Program Files\PostgreSQL\17\data",
        "C:\Program Files\PostgreSQL\16\data",
        "C:\Program Files\PostgreSQL\15\data",
        "C:\Program Files\PostgreSQL\14\data",
        "C:\Program Files\PostgreSQL\13\data",
    )
    foreach ($c in $candidates) {
        if (Test-Path "$c\postgresql.conf") { $dataDir = $c; break }
    }
}

if (-not $dataDir) {
    Write-Error "No se encontro el directorio de datos de PostgreSQL. Especificalo manualmente en la variable `$dataDir."
    exit 1
}

Write-OK "Directorio: $dataDir"

$pgConf  = Join-Path $dataDir "postgresql.conf"
$hbaConf = Join-Path $dataDir "pg_hba.conf"

# ── 2. postgresql.conf — listen_addresses = '*' ───────────────────────────────
Write-Step "Configurando listen_addresses en postgresql.conf"

$pgContent = Get-Content $pgConf -Raw

if ($pgContent -match "^listen_addresses\s*=\s*'\*'") {
    Write-OK "listen_addresses ya esta en '*', sin cambios."
} else {
    # Reemplazar la linea existente (comentada o no) o agregar al final
    if ($pgContent -match "(?m)^#?\s*listen_addresses\s*=") {
        $pgContent = $pgContent -replace "(?m)^#?\s*listen_addresses\s*=.*$", "listen_addresses = '*'"
        Write-OK "listen_addresses actualizado a '*'."
    } else {
        $pgContent += "`nlisten_addresses = '*'"
        Write-OK "listen_addresses agregado al final."
    }
    Set-Content $pgConf $pgContent -Encoding UTF8
}

# ── 3. pg_hba.conf — permitir conexiones remotas ─────────────────────────────
Write-Step "Configurando pg_hba.conf para conexiones remotas"

$hbaContent = Get-Content $hbaConf -Raw
$newRule    = "host    all    all    0.0.0.0/0    scram-sha-256"

if ($hbaContent -match [regex]::Escape($newRule)) {
    Write-OK "Regla de acceso remoto ya existe, sin cambios."
} else {
    Add-Content $hbaConf "`n$newRule"
    Write-OK "Regla agregada: $newRule"
}

# ── 4. Reiniciar servicio PostgreSQL ─────────────────────────────────────────
Write-Step "Reiniciando servicio PostgreSQL"

$svc = Get-Service "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($svc) {
    Restart-Service $svc.Name
    Write-OK "Servicio '$($svc.Name)' reiniciado."
} else {
    Write-Warn "No se encontro el servicio de PostgreSQL. Reinicialo manualmente."
}

# ── 5. Regla de firewall ──────────────────────────────────────────────────────
Write-Step "Abriendo puerto $PgPort en el firewall de Windows"

$ruleName = "PostgreSQL $PgPort"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

if ($existing) {
    Write-OK "Regla de firewall '$ruleName' ya existe."
} else {
    New-NetFirewallRule `
        -DisplayName $ruleName `
        -Direction   Inbound `
        -Protocol    TCP `
        -LocalPort   $PgPort `
        -Action      Allow | Out-Null
    Write-OK "Regla de firewall '$ruleName' creada."
}

# ── Resumen ───────────────────────────────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  PostgreSQL listo para conexiones remotas" -ForegroundColor Green
Write-Host "  Puerto: $PgPort  |  Usuario: postgres" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan
