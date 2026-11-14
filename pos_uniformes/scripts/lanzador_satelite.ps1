# Lanzador del satelite con AUTO-ACTUALIZACION por red (sin USB).
#
# Como funciona: al abrirlo, compara la version instalada en este kiosko
# contra la publicada por la PC principal en \\<servidor>\pos_updates.
# Si hay version nueva la copia (la app aun no corre, asi que nada esta
# bloqueado) y arranca el exe local. Si la PC principal esta apagada,
# simplemente arranca la version que ya tiene - nunca deja al kiosko tirado.
#
# Instalacion en un kiosko (UNA sola vez):
#   1. Copiar lanzador_satelite.bat y lanzador_satelite.ps1 desde
#      \\<servidor>\pos_updates a una carpeta local (p.ej. C:\PresupuestosSatelite).
#   2. Crear acceso directo al .bat en el Escritorio (y/o en la carpeta de
#      Inicio para que abra solo al prender la PC).
#   Despues de eso, las actualizaciones llegan solas.
#
# La ULTIMA linea de este archivo es su marca de fin: lanzador_satelite.bat
# revisa la de inicio (linea 1) y la de fin antes de abrirlo. No borrarlas.

$ErrorActionPreference = "SilentlyContinue"

# El servidor se lee del .env de la app instalada (misma fuente que usa la
# app); 192.168.0.10 solo como default de primera instalacion.
$serverHost = "192.168.0.10"
$appDir = Join-Path $env:LOCALAPPDATA "PresupuestosSatelite\app"
$envFile = Join-Path $appDir "pos_uniformes.env"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*POS_UNIFORMES_SERVER_HOST\s*=\s*(.+)$') {
            $serverHost = $Matches[1].Trim()
        }
    }
}
$share = "\\$serverHost\pos_updates\PresupuestosSatelite"
$updatesRoot = "\\$serverHost\pos_updates"

# Autenticarse al share en CADA arranque: Windows 11 bloquea el acceso como
# invitado y la credencial guardada con /persistent no siempre se reconecta
# a tiempo tras reiniciar. Si ya hay sesion, el error se ignora.
net use "\\$serverHost\pos_updates" pos2026 /user:kiosko /persistent:no 2>$null | Out-Null

# --- Archivos del lanzador: escritura que no puede quedar a medias ---------
# 2026-11-13: el Kiosko Principal se apago mientras el lanzador se copiaba a
# si mismo y al prender el .ps1 estaba lleno de ceros. Desde entonces NADA se
# escribe directo sobre un archivo bueno:
#   1. se copia a "<nombre>.nuevo" en la MISMA carpeta y se fuerza a disco;
#   2. se valida (no vacio, mismo tamano que el origen, su marca de inicio y,
#      el .ps1, su marca de fin y que PowerShell lo pueda leer sin errores);
#   3. solo entonces se pone en su lugar con [System.IO.File]::Replace.
# Replace (ReplaceFile de Windows) cambia el archivo en una sola operacion del
# sistema de archivos: si se va la luz queda el viejo o el nuevo, nunca uno a
# medias. Move-Item -Force en PowerShell 5.1 BORRA el destino y luego mueve:
# un apagon entre los dos pasos deja al kiosko sin lanzador.
$archivosLanzador = @("lanzador_satelite.ps1", "lanzador_satelite.bat", "reparar_satelite.bat")
$marcaFinPs1 = "# Fin del lanzador del satelite"
# Los .bat tambien llevan marca de fin en su ULTIMA linea: uno cortado empieza
# con "@echo off" pero le faltan etiquetas (cmd truena con "no se encuentra la
# etiqueta") y nadie revisa al .bat antes de abrirlo.
$marcasFinBat = @{
    "lanzador_satelite.bat" = "rem Fin del lanzador del satelite"
    "reparar_satelite.bat" = "rem Fin del reparador del satelite"
}

function Test-ArchivoLanzador($ruta, $nombre) {
    # $nombre es el nombre logico (lanzador_satelite.ps1, ...): decide la marca.
    $ErrorActionPreference = "Stop"
    try {
        if (-not (Test-Path -LiteralPath $ruta)) { return $false }
        $bytes = [System.IO.File]::ReadAllBytes($ruta)
        if ($bytes.Length -eq 0) { return $false }
        $texto = [System.Text.Encoding]::ASCII.GetString($bytes)
        $ordinal = [System.StringComparison]::Ordinal
        if ($nombre -like "*.ps1") {
            if (-not $texto.StartsWith("# Lanzador del satelite", $ordinal)) { return $false }
            if (-not $texto.TrimEnd().EndsWith($marcaFinPs1, $ordinal)) { return $false }
            $tokens = $null
            $errores = $null
            [void][System.Management.Automation.Language.Parser]::ParseInput($texto, [ref]$tokens, [ref]$errores)
            if ($errores -and ($errores.Count -gt 0)) { return $false }
        } else {
            if (-not $texto.StartsWith("@echo off", $ordinal)) { return $false }
            $finBat = $marcasFinBat[$nombre]
            if (-not $finBat) { return $false }
            # TrimEnd no quita ceros: un .bat con ceros al final tampoco pasa.
            $ultima = ($texto.TrimEnd().Split("`n"))[-1]
            if (-not $ultima.StartsWith($finBat, $ordinal)) { return $false }
        }
        return $true
    } catch {
        return $false
    }
}

function Restore-Huerfano($tmp, $destino, $nombre) {
    # ReplaceFile puede fallar DESPUES de quitar el archivo viejo
    # (ERROR_UNABLE_TO_MOVE_REPLACEMENT 1176/1177, p.ej. el antivirus abrio el
    # .nuevo): el destino ya no existe y el .nuevo validado es la UNICA copia.
    # Entonces se pone en su lugar en vez de borrarlo.
    if (Test-Path -LiteralPath $destino) { return $false }
    if (-not (Test-ArchivoLanzador $tmp $nombre)) { return $false }
    for ($intento = 1; $intento -le 5; $intento++) {
        try {
            [System.IO.File]::Move($tmp, $destino)
            return $true
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return $false
}

function Copy-Seguro($origen, $destino, $nombre) {
    # Deja $destino igual a $origen sin pasar nunca por un archivo a medias.
    $ErrorActionPreference = "Stop"
    $tmp = "$destino.nuevo"
    try {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
        $entrada = [System.IO.File]::OpenRead($origen)
        try {
            $salida = New-Object System.IO.FileStream($tmp, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
            try {
                $entrada.CopyTo($salida)
                $salida.Flush($true)   # a disco de verdad ANTES de cambiar el nombre
            } finally {
                $salida.Dispose()
            }
        } finally {
            $entrada.Dispose()
        }
        if ((Get-Item -LiteralPath $tmp).Length -ne (Get-Item -LiteralPath $origen).Length) { throw "tamano distinto" }
        if (-not (Test-ArchivoLanzador $tmp $nombre)) { throw "no paso la validacion" }
        if (Test-Path -LiteralPath $destino) {
            # [NullString]::Value: con $null PowerShell mandaria "" y Replace falla.
            [System.IO.File]::Replace($tmp, $destino, [NullString]::Value)
        } else {
            [System.IO.File]::Move($tmp, $destino)
        }
        return $true
    } catch {
        if (Restore-Huerfano $tmp $destino $nombre) { return $true }
        # Sin destino, un .nuevo valido no se borra: el proximo arranque lo
        # pone en su lugar (ver la limpieza de abajo).
        if ((Test-Path -LiteralPath $destino) -or -not (Test-ArchivoLanzador $tmp $nombre)) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
        return $false
    }
}

function Test-MismoArchivo($a, $b) {
    if (-not (Test-Path -LiteralPath $a) -or -not (Test-Path -LiteralPath $b)) { return $false }
    if ((Get-Item -LiteralPath $a).Length -ne (Get-Item -LiteralPath $b).Length) { return $false }
    return ((Get-FileHash -LiteralPath $a).Hash -eq (Get-FileHash -LiteralPath $b).Hash)
}

function Update-ArchivosLanzador($origenDir) {
    # Trae del share los archivos del lanzador que cambiaron (aplica en el
    # SIGUIENTE arranque). Si no cambio nada, no escribe nada.
    foreach ($f in $archivosLanzador) {
        $origen = Join-Path $origenDir $f
        $destino = Join-Path $PSScriptRoot $f
        if (-not (Test-Path -LiteralPath $origen)) { continue }
        if (Test-MismoArchivo $origen $destino) { continue }
        # Lo publicado a medias (o roto) no se copia: el kiosko se queda con el suyo.
        if (-not (Test-ArchivoLanzador $origen $f)) { continue }
        if (Copy-Seguro $origen $destino $f) {
            Write-Host "Lanzador actualizado: $f"
        } else {
            Write-Host "(No se pudo actualizar $f; se intenta en el proximo arranque)"
        }
    }
}

function Save-RespaldoLanzador {
    # Copia buena local para lanzador_satelite.bat y reparar_satelite.bat:
    # si el .ps1 se dana, lo restauran de aqui aunque la PC principal no este.
    foreach ($f in @("lanzador_satelite.ps1", "lanzador_satelite.bat")) {
        $actual = Join-Path $PSScriptRoot $f
        $respaldo = "$actual.respaldo"
        if (-not (Test-ArchivoLanzador $actual $f)) { continue }
        if (Test-MismoArchivo $actual $respaldo) { continue }
        [void](Copy-Seguro $actual $respaldo $f)
    }
}

# Restos de una copia interrumpida (apagon): se borran. Solo si el archivo
# de verdad ya no existe (Replace fallo a medias) y el .nuevo es valido, el
# .nuevo se pone en su lugar.
foreach ($f in $archivosLanzador) {
    $viejo = Join-Path $PSScriptRoot $f
    if (-not (Restore-Huerfano "$viejo.nuevo" $viejo $f)) {
        Remove-Item -LiteralPath "$viejo.nuevo" -Force -ErrorAction SilentlyContinue
    }
    if (-not (Restore-Huerfano "$viejo.respaldo.nuevo" "$viejo.respaldo" $f)) {
        Remove-Item -LiteralPath "$viejo.respaldo.nuevo" -Force -ErrorAction SilentlyContinue
    }
}

function Get-VersionDe($dir) {
    $file = Join-Path $dir "VERSION.txt"
    if (Test-Path $file) { (Get-Content $file -Raw).Trim() } else { "" }
}

$versionLocal = Get-VersionDe $appDir
$versionRemota = ""
if (Test-Path $share) { $versionRemota = Get-VersionDe $share }

if ($versionRemota -and ($versionRemota -ne $versionLocal)) {
    # Si la app vieja sigue viva (su boton Actualizar cerraba la ventana
    # pero no el proceso), aqui se cierra de verdad: con el proceso vivo
    # robocopy no puede copiar y la instancia nueva choca con el candado
    # ("ya se esta ejecutando el satelite").
    $viva = Get-Process "PresupuestosSatelite*" -ErrorAction SilentlyContinue
    if ($viva) {
        Write-Host "Cerrando el satelite abierto para poder actualizar..."
        $viva | Stop-Process -Force
        Start-Sleep -Seconds 3
    }
    Write-Host "Actualizando satelite: '$versionLocal' -> '$versionRemota' ..."
    Write-Host "(la primera vez copia ~300 MB y tarda unos minutos; se ve avanzar)"
    # /NDL /NP: muestra cada archivo copiado (progreso visible) sin spam.
    # /XF VERSION.txt: la version se escribe HASTA el final y solo si la copia
    # quedo completa. Si algo falla (red, antivirus), el kiosko conserva la
    # version vieja y lo vuelve a intentar en el proximo arranque, en vez de
    # quedarse con un .exe a medias ("Could not load PyInstaller's PKG").
    robocopy $share $appDir /MIR /R:5 /W:2 /NDL /NP /XF VERSION.txt
    $codigo = $LASTEXITCODE
    $exeRemoto = Get-ChildItem $share -Filter "*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    $copiaOk = $false
    if ($exeRemoto) {
        $exeLocal = Join-Path $appDir $exeRemoto.Name
        if (($codigo -lt 8) -and (Test-Path $exeLocal) -and ((Get-Item $exeLocal).Length -eq $exeRemoto.Length)) {
            $copiaOk = $true
        } else {
            Write-Host "La copia no quedo completa; reintentando el programa..."
            Copy-Item $exeRemoto.FullName $exeLocal -Force -ErrorAction SilentlyContinue
            $copiaOk = (Test-Path $exeLocal) -and ((Get-Item $exeLocal).Length -eq $exeRemoto.Length)
        }
    }
    if ($copiaOk) {
        Copy-Item (Join-Path $share "VERSION.txt") (Join-Path $appDir "VERSION.txt") -Force -ErrorAction SilentlyContinue
        Write-Host "Actualizado."
    } else {
        Write-Host ""
        Write-Host "*** No se pudo copiar completo (codigo $codigo). Se vuelve a intentar al abrir de nuevo. ***"
        Write-Host "Si se repite: revisa la red o el antivirus de este kiosko."
        Start-Sleep -Seconds 4
    }
}

$exe = Get-ChildItem $appDir -Filter "*.exe" -ErrorAction SilentlyContinue |
    Select-Object -First 1

# Red de seguridad: si el programa local no pesa lo mismo que el del servidor
# quedo a medias (copia interrumpida, antivirus). Se copia de nuevo aunque la
# version diga que esta al dia; si no, arranca y truena con el error de PKG.
if ($exe -and (Test-Path $share)) {
    $exeRemoto = Get-ChildItem $share -Filter "*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($exeRemoto -and ($exeRemoto.Name -eq $exe.Name) -and ($exeRemoto.Length -ne $exe.Length)) {
        Write-Host "El programa quedo incompleto; copiandolo de nuevo..."
        Get-Process "PresupuestosSatelite*" -ErrorAction SilentlyContinue | Stop-Process -Force
        Start-Sleep -Seconds 2
        Copy-Item $exeRemoto.FullName $exe.FullName -Force -ErrorAction SilentlyContinue
        $exe = Get-ChildItem $appDir -Filter "*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    }
}

# Acceso directo en el Escritorio (se crea solo la primera vez, con el
# icono de la app): el kiosko queda auto-instalado sin pasos manuales.
try {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $lnkPath = Join-Path $desktop "Presupuestos Satelite.lnk"
    if ($desktop -and -not (Test-Path $lnkPath)) {
        $shell = New-Object -ComObject WScript.Shell
        $lnk = $shell.CreateShortcut($lnkPath)
        $lnk.TargetPath = Join-Path $PSScriptRoot "lanzador_satelite.bat"
        $lnk.WorkingDirectory = $PSScriptRoot
        $lnk.Description = "Abre el satelite (se actualiza solo)"
        if ($exe) { $lnk.IconLocation = "$($exe.FullName),0" }
        $lnk.Save()
        Write-Host "Acceso directo creado en el Escritorio."
    }
} catch {
    # Sin acceso directo no pasa nada: la app abre igual.
}

$arranco = $false
if ($exe) {
    $proceso = Start-Process $exe.FullName -WorkingDirectory $appDir -PassThru
    if ($proceso) { $arranco = $true }
}

# Este lanzador llego hasta abrir la app: es una copia buena. Se respalda
# ANTES de refrescarlo del share, para que el respaldo sea el que si funciono.
if ($arranco) { Save-RespaldoLanzador }

# El lanzador tambien se refresca a si mismo desde el share (aplica en el
# SIGUIENTE arranque): instalar mejoras del lanzador ya no requiere USB.
# Va despues de abrir la app: el kiosko no espera por esto.
if (Test-Path $share) { Update-ArchivosLanzador $updatesRoot }

if (-not $exe) {
    Write-Host ""
    Write-Host "No hay app instalada en este kiosko y no se alcanzo la PC principal."
    Write-Host "Enciende la PC principal (o revisa la red) y vuelve a abrir este acceso."
    Read-Host "Enter para cerrar"
}
# Fin del lanzador del satelite
