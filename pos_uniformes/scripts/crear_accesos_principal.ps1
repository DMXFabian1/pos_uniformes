# Crea los accesos directos del Escritorio en la PC PRINCIPAL:
#   - "POS Uniformes"  -> abre la app (sin consola)
#   - "Actualizar POS" -> pull + migraciones + build + publicar a kioskos
# Correr una vez con: scripts\crear_accesos_principal.bat

$repo = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
$icono = Join-Path $repo "assets\app_icon.ico"

$lnk = $shell.CreateShortcut((Join-Path $desktop "POS Uniformes.lnk"))
$lnk.TargetPath = Join-Path $repo "scripts\abrir_pos.bat"
$lnk.WorkingDirectory = $repo
$lnk.Description = "Abre el POS principal"
if (Test-Path $icono) { $lnk.IconLocation = "$icono,0" }
$lnk.Save()
Write-Host "Creado: POS Uniformes"

$lnk = $shell.CreateShortcut((Join-Path $desktop "Actualizar POS.lnk"))
$lnk.TargetPath = Join-Path $repo "scripts\actualizar_pc_principal.bat"
$lnk.WorkingDirectory = $repo
$lnk.Description = "Actualiza el POS y publica a los kioskos"
$lnk.Save()
Write-Host "Creado: Actualizar POS"

Write-Host ""
Write-Host "Listo: revisa el Escritorio."
