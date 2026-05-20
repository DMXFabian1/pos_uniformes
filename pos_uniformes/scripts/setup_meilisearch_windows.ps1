<#
.SYNOPSIS
    Instala Meilisearch en Windows y lo configura como tarea programada (auto-start).

.DESCRIPTION
    1. Descarga el binario de Meilisearch para Windows (v1.44.0)
    2. Lo coloca en C:\Meilisearch\
    3. Crea carpeta de datos en C:\Meilisearch\data\
    4. Registra una tarea programada que inicia Meilisearch al encender la PC
    5. Arranca Meilisearch inmediatamente
    6. Indexa el catalogo desde la DB del POS

.EXAMPLE
    # Ejecutar como Administrador:
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\scripts\setup_meilisearch_windows.ps1
#>

param(
    [string]$InstallDir = "C:\Meilisearch",
    [string]$Version = "v1.14.0",
    [int]$Port = 7700
)

$ErrorActionPreference = "Stop"

# ── 1. Crear directorio ─────────────────────────────────────────────────
Write-Host "`n=== Instalando Meilisearch ===" -ForegroundColor Cyan

if (!(Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Write-Host "  Creado: $InstallDir"
}

$DataDir = Join-Path $InstallDir "data"
if (!(Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

$MeiliBin = Join-Path $InstallDir "meilisearch.exe"

# ── 2. Descargar binario ────────────────────────────────────────────────
if (Test-Path $MeiliBin) {
    Write-Host "  Binario ya existe: $MeiliBin" -ForegroundColor Yellow
    $redownload = Read-Host "  Descargar de nuevo? (s/n)"
    if ($redownload -ne "s") {
        Write-Host "  Usando binario existente."
    } else {
        Remove-Item $MeiliBin -Force
    }
}

if (!(Test-Path $MeiliBin)) {
    $url = "https://github.com/meilisearch/meilisearch/releases/download/$Version/meilisearch-windows-amd64.exe"
    Write-Host "  Descargando desde: $url"
    Write-Host "  Esto puede tardar 1-2 minutos..." -ForegroundColor Yellow

    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $url -OutFile $MeiliBin -UseBasicParsing
        Write-Host "  Descargado: $MeiliBin" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR descargando. Descarga manual:" -ForegroundColor Red
        Write-Host "  $url" -ForegroundColor Yellow
        Write-Host "  Guarda como: $MeiliBin"
        exit 1
    }
}

# ── 3. Detener instancia existente ──────────────────────────────────────
$existing = Get-Process -Name "meilisearch" -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "  Deteniendo Meilisearch existente..."
    Stop-Process -Name "meilisearch" -Force
    Start-Sleep -Seconds 2
}

# ── 4. Crear tarea programada (auto-start al encender PC) ──────────────
$TaskName = "MeilisearchPOS"

$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "  Tarea programada ya existe, actualizando..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action = New-ScheduledTaskAction `
    -Execute $MeiliBin `
    -Argument "--no-analytics --db-path `"$DataDir`" --http-addr 127.0.0.1:$Port" `
    -WorkingDirectory $InstallDir

$trigger = New-ScheduledTaskTrigger -AtLogon
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Meilisearch para POS Uniformes - busqueda rapida de catalogo" `
    -RunLevel Highest | Out-Null

Write-Host "  Tarea programada '$TaskName' registrada (auto-start al encender)" -ForegroundColor Green

# ── 5. Iniciar Meilisearch ahora ────────────────────────────────────────
Write-Host "  Iniciando Meilisearch en puerto $Port..."
Start-Process -FilePath $MeiliBin `
    -ArgumentList "--no-analytics", "--db-path", "`"$DataDir`"", "--http-addr", "127.0.0.1:$Port" `
    -WindowStyle Hidden

Start-Sleep -Seconds 3

# Verificar que esta corriendo
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -Method Get
    if ($health.status -eq "available") {
        Write-Host "  Meilisearch corriendo OK" -ForegroundColor Green
    }
} catch {
    Write-Host "  ADVERTENCIA: Meilisearch no responde aun. Puede tardar unos segundos." -ForegroundColor Yellow
    Write-Host "  Verifica manualmente: curl http://127.0.0.1:$Port/health"
}

# ── 6. Indexar catalogo desde la DB ─────────────────────────────────────
Write-Host "`n=== Indexando catalogo ===" -ForegroundColor Cyan

$PosDir = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $PosDir ".venv\Scripts\python.exe"

if (Test-Path $VenvPython) {
    Write-Host "  Ejecutando indexacion con $VenvPython..."
    Push-Location (Split-Path -Parent $PosDir)
    try {
        & $VenvPython -c @"
import sys
sys.path.insert(0, '.')
from pos_uniformes.database.connection import get_session
from pos_uniformes.services.meilisearch_service import configure_index, index_from_db
configure_index()
with get_session() as session:
    count = index_from_db(session)
    print(f'  Indexados: {count} documentos')
"@
    } catch {
        Write-Host "  Error al indexar: $_" -ForegroundColor Yellow
        Write-Host "  La indexacion se hara automaticamente al abrir el POS."
    }
    Pop-Location
} else {
    Write-Host "  No se encontro el venv. La indexacion se hara al abrir el POS." -ForegroundColor Yellow
}

# ── Resumen ─────────────────────────────────────────────────────────────
Write-Host "`n=== Instalacion completa ===" -ForegroundColor Green
Write-Host "  Binario:    $MeiliBin"
Write-Host "  Datos:      $DataDir"
Write-Host "  Puerto:     $Port"
Write-Host "  Auto-start: Tarea '$TaskName' (al iniciar sesion)"
Write-Host "  Health:     http://127.0.0.1:$Port/health"
Write-Host ""
