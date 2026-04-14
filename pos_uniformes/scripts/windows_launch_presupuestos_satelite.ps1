param(
    [string]$TargetDir = "C:\Users\Daniel\Desktop\PresupuestosSatelite-2026.04.07",
    [string]$DbHost = "192.168.0.9",
    [string]$DbPort = "5432",
    [string]$DbName = "pos_uniformes",
    [string]$DbUser = "postgres",
    [string]$DbPassword = "1234"
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$message) {
    Write-Host ""
    Write-Host $message -ForegroundColor Cyan
}

function Ensure-EnvFile(
    [string]$Path,
    [string]$Host,
    [string]$Port,
    [string]$Name,
    [string]$User,
    [string]$Password
) {
    $desiredContent = @"
POS_UNIFORMES_DB_HOST=$Host
POS_UNIFORMES_DB_PORT=$Port
POS_UNIFORMES_DB_NAME=$Name
POS_UNIFORMES_DB_USER=$User
POS_UNIFORMES_DB_PASSWORD=$Password
POS_UNIFORMES_DB_ECHO=0
POS_UNIFORMES_AUTO_CREATE_SCHEMA=0
POS_UNIFORMES_BACKUP_EXTERNAL_DIR=
"@

    Set-Content -Path $Path -Value $desiredContent -Encoding ascii
}

if (-not (Test-Path $TargetDir)) {
    throw "No existe la carpeta del satelite: $TargetDir"
}

Set-Location $TargetDir

$envFile = Join-Path $TargetDir "pos_uniformes.env"
$exe = Get-ChildItem $TargetDir -Filter "*.exe" -File | Select-Object -First 1

if (-not $exe) {
    throw "No encontre ningun .exe en $TargetDir"
}

Write-Step "1. Verificando o regenerando pos_uniformes.env"
Ensure-EnvFile -Path $envFile -Host $DbHost -Port $DbPort -Name $DbName -User $DbUser -Password $DbPassword
Write-Host "ENV listo: $envFile" -ForegroundColor Green

Write-Step "2. Probando conexion con la PC principal"
$connection = Test-NetConnection $DbHost -Port ([int]$DbPort) -WarningAction SilentlyContinue
if (-not $connection.TcpTestSucceeded) {
    Write-Host "No fue posible conectar con $DbHost`:$DbPort" -ForegroundColor Red
    Write-Host "Revisa estos puntos antes de abrir la app:" -ForegroundColor Yellow
    Write-Host "- La PC principal debe estar encendida."
    Write-Host "- Ambas PCs deben estar en la misma red."
    Write-Host "- PostgreSQL debe seguir aceptando conexiones remotas."
    Write-Host "- SourceAddress actual: $($connection.SourceAddress)"
    exit 1
}

Write-Host "Conexion OK hacia $DbHost`:$DbPort" -ForegroundColor Green

Write-Step "3. Abriendo la app satelite"
Start-Process -FilePath $exe.FullName
Write-Host "App iniciada: $($exe.Name)" -ForegroundColor Green
