# ═══════════════════════════════════════════════════════════════════
# Deploy módulo Bodega — copia archivos nuevos y modificados al PC Windows
# Ejecutar desde PowerShell en la PC principal (192.168.0.10)
# ═══════════════════════════════════════════════════════════════════

$REPO = "C:\Users\Pc\pos_uniformes\pos_uniformes"

Write-Host "`n=== Deploy modulo Bodega ===" -ForegroundColor Cyan
Write-Host "Destino: $REPO`n"

# --- Crear directorios si no existen ---
$dirs = @(
    "$REPO\pos_uniformes\migrations\versions",
    "$REPO\pos_uniformes\services",
    "$REPO\pos_uniformes\tests",
    "$REPO\pos_uniformes\ui\dialogs",
    "$REPO\pos_uniformes\ui\views"
)
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
        Write-Host "  Creado: $d" -ForegroundColor Yellow
    }
}

# --- Archivos nuevos (6) ---
$nuevos = @(
    "pos_uniformes\migrations\versions\a1b3c5d7e9f0_add_bodega_module.py",
    "pos_uniformes\services\bodega_service.py",
    "pos_uniformes\tests\test_bodega_service.py",
    "pos_uniformes\ui\dialogs\bodega_ingreso_dialog.py",
    "pos_uniformes\ui\dialogs\bodega_ubicaciones_dialog.py",
    "pos_uniformes\ui\views\bodega_view.py"
)

# --- Archivos modificados (3) ---
$modificados = @(
    "pos_uniformes\database\models.py",
    "pos_uniformes\ui\main_window.py",
    "pos_uniformes\utils\qr_generator.py"
)

# --- Backup de archivos modificados ---
Write-Host "Haciendo backup de archivos modificados..." -ForegroundColor Yellow
foreach ($f in $modificados) {
    $ruta = Join-Path $REPO $f
    if (Test-Path $ruta) {
        $backup = "$ruta.bak-$(Get-Date -Format 'yyyyMMdd-HHmm')"
        Copy-Item $ruta $backup
        Write-Host "  Backup: $f -> .bak" -ForegroundColor DarkGray
    }
}

Write-Host ""

# --- Instrucciones ---
Write-Host "ARCHIVOS NUEVOS (copiar desde Mac):" -ForegroundColor Green
foreach ($f in $nuevos) {
    Write-Host "  + $f"
}

Write-Host "`nARCHIVOS MODIFICADOS (copiar desde Mac, ya tienen backup):" -ForegroundColor Yellow
foreach ($f in $modificados) {
    Write-Host "  ~ $f"
}

# --- Si se ejecuta con git pull (recomendado) ---
Write-Host "`n=== OPCION RECOMENDADA: git pull ===" -ForegroundColor Cyan
Write-Host "Si ya hiciste push desde Mac, simplemente ejecuta:"
Write-Host "  cd $REPO" -ForegroundColor White
Write-Host "  git pull origin main" -ForegroundColor White

# --- Migración ---
Write-Host "`n=== POST-DEPLOY ===" -ForegroundColor Cyan
Write-Host "Ejecutar migracion de base de datos:"
Write-Host "  cd $REPO" -ForegroundColor White
Write-Host "  .\.venv\Scripts\python.exe -m alembic upgrade head" -ForegroundColor White

# --- Tests ---
Write-Host "`nVerificar tests de bodega:"
Write-Host "  .\.venv\Scripts\python.exe -m unittest pos_uniformes.tests.test_bodega_service -v" -ForegroundColor White

Write-Host "`n=== Listo ===" -ForegroundColor Green
