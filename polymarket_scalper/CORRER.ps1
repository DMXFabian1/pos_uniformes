# Arranca todo lo necesario para acumular muestra, desde la terminal de VS Code.
#
#   .\CORRER.ps1              actualiza, comprueba la instalación y arranca bot + panel
#   .\CORRER.ps1 -SoloBot     solo el bot, sin panel
#   .\CORRER.ps1 -SinPull     no descarga cambios (útil si estás sin red)
#   .\CORRER.ps1 -Informe     no arranca nada: solo enseña cómo va la medición
#
# El bot queda en esta misma ventana. Ctrl+C lo detiene guardando lo que tenga pendiente.
param(
    [switch]$SoloBot,
    [switch]$SinPull,
    [switch]$Informe
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

function Paso($n, $texto) { Write-Host "`n[$n] $texto" -ForegroundColor Cyan }
function Aviso($texto) { Write-Host "     $texto" -ForegroundColor DarkGray }

$exe = Join-Path $PSScriptRoot ".venv\Scripts\scalper.exe"

# ---------------------------------------------------------------- 1. traer la última versión
if (-not $SinPull -and -not $Informe) {
    Paso 1 "Descargando la última versión"
    try {
        $sucio = (git status --porcelain)
        if ($sucio) {
            Aviso "Tienes cambios locales sin guardar. No se descarga nada para no pisarlos."
            Aviso "Si no los quieres: git checkout -- .   y vuelve a ejecutar este script."
        } else {
            git pull --ff-only
        }
    } catch {
        Aviso "No se pudo actualizar ($($_.Exception.Message)). Se sigue con lo que hay."
    }
}

# ---------------------------------------------------------------- 2. comprobar la instalación
Paso 2 "Comprobando la instalación"
if (-not (Test-Path $exe)) {
    Aviso "Falta instalar. Lanzo el instalador; tarda un par de minutos la primera vez."
    $instalador = Join-Path $PSScriptRoot "deploy\instalar-windows.ps1"
    & powershell -ExecutionPolicy Bypass -File "$instalador"
    if (-not (Test-Path $exe)) {
        Write-Host "`nLa instalación no terminó bien. Revisa los mensajes de arriba." -ForegroundColor Red
        exit 1
    }
} else {
    Aviso "Instalado."
}
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "logs") | Out-Null

# ---------------------------------------------------------------- solo informe
if ($Informe) {
    & $exe -c config.yaml validacion
    Write-Host ""
    & $exe -c config.yaml experimentos
    exit 0
}

# ---------------------------------------------------------------- 3. congelar la versión del motor
Paso 3 "Congelando la versión del motor"
Aviso "Todo lo que se mida a partir de ahora lleva esta marca. Si cambias la configuración,"
Aviso "empieza otro experimento y los datos quedan separados."
& $exe -c config.yaml experimentos --congelar --nota "muestra desde VS Code"

# ---------------------------------------------------------------- 4. panel en otra ventana
if (-not $SoloBot) {
    Paso 4 "Abriendo el panel en otra ventana"
    $orden = "Set-Location '$PSScriptRoot'; `$env:PYTHONUTF8='1'; " +
             "& '$exe' -c config.yaml --log-file logs\panel.log dashboard"
    Start-Process powershell -ArgumentList "-NoExit -ExecutionPolicy Bypass -Command `"$orden`""
    Start-Sleep -Seconds 4
    Start-Process "http://127.0.0.1:8787"
    Aviso "Panel en http://127.0.0.1:8787 (pestaña Ejecución: ahí está la medición)"
}

# ---------------------------------------------------------------- 5. el bot, en esta ventana
Paso 5 "Arrancando el bot"
Write-Host ""
Write-Host "  Déjalo corriendo el tiempo que puedas. Un día entero da unas cien operaciones," -ForegroundColor Yellow
Write-Host "  que es el mínimo para que el semáforo deje de estar en amarillo." -ForegroundColor Yellow
Write-Host "  Ctrl+C lo detiene guardando todo lo pendiente." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Para ver cómo va, en otra terminal:  .\CORRER.ps1 -Informe" -ForegroundColor DarkGray
Write-Host ""
& $exe -c config.yaml --log-file logs\bot.log paper
