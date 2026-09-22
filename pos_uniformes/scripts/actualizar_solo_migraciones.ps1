# =====================================================
#  Trae lo nuevo del repositorio y aplica SOLO las
#  migraciones de base de datos (sin build ni publicar
#  a kioskos). Para destrabar la principal rapido.
#
#  Uso, en PowerShell, en la carpeta del repo:
#     .\scripts\actualizar_solo_migraciones.ps1
# =====================================================
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "=== 1/3 Trayendo lo nuevo del repositorio ===" -ForegroundColor Cyan
git pull
if ($LASTEXITCODE -ne 0) { Write-Host "No se pudo hacer git pull." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "=== 2/3 Version de la base ANTES ===" -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m alembic current

Write-Host ""
Write-Host "=== 3/3 Aplicando migraciones ===" -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Write-Host "Fallaron las migraciones." -ForegroundColor Red; exit 1 }

Write-Host ""
.\.venv\Scripts\python.exe -m alembic current
Write-Host ""
Write-Host "LISTO. La base quedo al dia." -ForegroundColor Green
Write-Host "Si quieres ademas publicar a los kioskos, corre scripts\actualizar_pc_principal.bat" -ForegroundColor Yellow
