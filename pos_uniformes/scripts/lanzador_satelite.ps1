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

# Autenticarse al share en CADA arranque: Windows 11 bloquea el acceso como
# invitado y la credencial guardada con /persistent no siempre se reconecta
# a tiempo tras reiniciar. Si ya hay sesion, el error se ignora.
net use "\\$serverHost\pos_updates" pos2026 /user:kiosko /persistent:no 2>$null | Out-Null

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

# El lanzador tambien se refresca a si mismo desde el share (aplica en el
# SIGUIENTE arranque): instalar mejoras del lanzador ya no requiere USB.
if (Test-Path $share) {
    $updatesRoot = "\\$serverHost\pos_updates"
    foreach ($f in @("lanzador_satelite.ps1", "lanzador_satelite.bat")) {
        Copy-Item (Join-Path $updatesRoot $f) $PSScriptRoot -Force -ErrorAction SilentlyContinue
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

if ($exe) {
    Start-Process $exe.FullName -WorkingDirectory $appDir
} else {
    Write-Host ""
    Write-Host "No hay app instalada en este kiosko y no se alcanzo la PC principal."
    Write-Host "Enciende la PC principal (o revisa la red) y vuelve a abrir este acceso."
    Read-Host "Enter para cerrar"
}
