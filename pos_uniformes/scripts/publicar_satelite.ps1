param(
    # Carpeta de la build a publicar. Sin ella, la mas reciente de dist\.
    [string]$BundleDir = ""
)

# Publica la build del kiosko en C:\pos_updates para que cada kiosko la tome
# al abrir. Antes de pisar lo publicado lo guarda en PresupuestosSatelite_anterior:
# de ahi sale "volver a la version anterior" (scripts\volver_version_anterior.bat).
#
# Lo llaman build_presupuestos_satelite_windows.ps1 (cuando publica el mismo) y
# scripts\actualizar.py (que publica DESPUES de migrar la base).

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $BundleDir) {
    $ultima = Get-ChildItem (Join-Path $projectRoot "dist") -Directory -Filter "PresupuestosSatelite-*" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $ultima) {
        Write-Host "*** No hay ninguna build en dist\ para publicar. ***"
        exit 1
    }
    $BundleDir = $ultima.FullName
}
$versionFile = Join-Path $BundleDir "VERSION.txt"
if (-not (Test-Path $versionFile)) {
    Write-Host "*** La build de $BundleDir no trae VERSION.txt: no se publica. ***"
    exit 1
}
$publishedVersion = (Get-Content $versionFile -Raw).Trim()

$updatesDir = $env:POS_UNIFORMES_UPDATES_DIR
if (-not $updatesDir) { $updatesDir = "C:\pos_updates" }
if (-not (Test-Path $updatesDir)) {
    Write-Host "  (No existe $updatesDir - no se publico para kioskos)"
    exit 0
}

$publishDir = Join-Path $updatesDir "PresupuestosSatelite"
$anteriorDir = Join-Path $updatesDir "PresupuestosSatelite_anterior"

# Guardar lo que estaba publicado, si es OTRA version (republicar la misma no
# debe pisar la anterior de verdad con una copia de si misma).
$versionPublicada = ""
$publicadaFile = Join-Path $publishDir "VERSION.txt"
if (Test-Path $publicadaFile) { $versionPublicada = (Get-Content $publicadaFile -Raw).Trim() }
if ($versionPublicada -and ($versionPublicada -ne $publishedVersion)) {
    Write-Host "  Guardando la version anterior ($versionPublicada)..."
    robocopy $publishDir $anteriorDir /MIR /R:2 /W:2 | Out-Null
    if ($LASTEXITCODE -ge 8) {
        Write-Host "  (No se pudo guardar la version anterior - se publica de todas formas)"
    }
}

robocopy $BundleDir $publishDir /MIR /R:2 /W:2 | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Host "*** No se pudo copiar la build a $publishDir (robocopy $LASTEXITCODE). ***"
    exit 1
}
# VERSION.txt lleva fecha + commit: los kioskos se actualizan solos en CADA
# build publicada. Se escribe al final: es lo que les dice "ya hay algo nuevo".
Set-Content -Path (Join-Path $publishDir "VERSION.txt") -Value $publishedVersion

# Los archivos del lanzador se publican con temporal + reemplazo: un kiosko
# que arranca justo ahora lee el viejo o el nuevo, nunca uno a medias. Se
# copia a "<nombre>.nuevo" en la misma carpeta, se fuerza a disco, se revisa
# el tamano y se pone en su lugar con [System.IO.File]::Replace (una sola
# operacion del sistema de archivos; Move-Item -Force borra y luego mueve).
function Publicar-Archivo($nombre, [switch]$Opcional) {
    $origen = Join-Path $PSScriptRoot $nombre
    $destino = Join-Path $updatesDir $nombre
    $tmp = "$destino.nuevo"
    $copiado = $false   # el .nuevo es de ESTA publicacion y llego completo
    try {
        if (-not (Test-Path -LiteralPath $origen)) { throw "no existe $origen" }
        if ($nombre -eq "lanzador_satelite.ps1") {
            # Un lanzador que PowerShell no puede leer no se publica: los
            # kioskos lo rechazarian igual, pero mejor enterarse aqui.
            $texto = [System.IO.File]::ReadAllText($origen)
            $tokens = $null
            $errores = $null
            [void][System.Management.Automation.Language.Parser]::ParseInput($texto, [ref]$tokens, [ref]$errores)
            if ($errores -and ($errores.Count -gt 0)) { throw "lanzador_satelite.ps1 tiene errores de sintaxis" }
            if (-not $texto.TrimEnd().EndsWith("# Fin del lanzador del satelite", [System.StringComparison]::Ordinal)) {
                throw "lanzador_satelite.ps1 no termina con su marca de fin"
            }
        }
        # Los .bat del lanzador tambien: los kioskos rechazan uno sin su marca.
        $finBat = @{
            "lanzador_satelite.bat" = "rem Fin del lanzador del satelite"
            "reparar_satelite.bat" = "rem Fin del reparador del satelite"
        }[$nombre]
        if ($finBat) {
            $ultima = ([System.IO.File]::ReadAllText($origen).TrimEnd().Split("`n"))[-1]
            if (-not $ultima.StartsWith($finBat, [System.StringComparison]::Ordinal)) {
                throw "$nombre no termina con su marca de fin"
            }
        }
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
        $entrada = [System.IO.File]::OpenRead($origen)
        try {
            $salida = New-Object System.IO.FileStream($tmp, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
            try {
                $entrada.CopyTo($salida)
                $salida.Flush($true)
            } finally {
                $salida.Dispose()
            }
        } finally {
            $entrada.Dispose()
        }
        if ((Get-Item -LiteralPath $tmp).Length -ne (Get-Item -LiteralPath $origen).Length) { throw "copia incompleta de $nombre" }
        $copiado = $true
        # Si un kiosko lo esta leyendo en este instante, Replace puede fallar:
        # se reintenta unos segundos.
        for ($intento = 1; $true; $intento++) {
            try {
                if (Test-Path -LiteralPath $destino) {
                    [System.IO.File]::Replace($tmp, $destino, [NullString]::Value)
                } else {
                    [System.IO.File]::Move($tmp, $destino)
                }
                break
            } catch {
                if ($intento -ge 5) { throw }
                Start-Sleep -Seconds 1
            }
        }
    } catch {
        # Replace puede fallar DESPUES de quitar el publicado (ReplaceFile:
        # ERROR_UNABLE_TO_MOVE_REPLACEMENT 1176/1177): sin destino, el .nuevo
        # completo es la unica copia y se pone en su lugar, nunca se borra.
        $error1 = $_
        $rescatado = $false
        $conservar = $false
        try {
            if ($copiado -and (Test-Path -LiteralPath $tmp) -and -not (Test-Path -LiteralPath $destino) -and
                ((Get-Item -LiteralPath $tmp).Length -eq (Get-Item -LiteralPath $origen).Length)) {
                $conservar = $true
                [System.IO.File]::Move($tmp, $destino)
                $rescatado = $true
            }
        } catch { }
        if ($rescatado) { return }
        if (-not $conservar) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
        if ($Opcional) {
            Write-Host "  (No se publico $nombre`: $($error1.Exception.Message))"
            return
        }
        throw $error1
    }
}

# El lanzador tambien se publica: instalar un kiosko nuevo = copiar
# lanzador_satelite.bat + .ps1 desde la carpeta compartida.
Publicar-Archivo "lanzador_satelite.ps1"
Publicar-Archivo "lanzador_satelite.bat"
# Reparador para el kiosko (cuando el .exe se copia a medias o el lanzador
# se dano).
Publicar-Archivo "reparar_satelite.bat" -Opcional
# El instalador del servidor de impresion del kiosko tambien: ahi no hay
# repo ni Python, asi que tiene que llegar por la carpeta compartida.
Publicar-Archivo "instalar_servidor_impresion_kiosko.bat" -Opcional
Write-Host "  Publicado para kioskos en: $publishDir ($publishedVersion)"
exit 0
