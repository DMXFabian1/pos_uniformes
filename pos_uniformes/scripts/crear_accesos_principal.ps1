# Crea EL acceso directo del Escritorio en la PC PRINCIPAL:
#   "POS Uniformes" -> busca actualizaciones y abre el POS (abrir_pos.bat)
# Correr una vez con: scripts\crear_accesos_principal.bat

$repo = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
$icono = Join-Path $repo "assets\app_icon.ico"

$lnk = $shell.CreateShortcut((Join-Path $desktop "POS Uniformes.lnk"))
$lnk.TargetPath = Join-Path $repo "scripts\abrir_pos.bat"
$lnk.WorkingDirectory = $repo
$lnk.Description = "Busca actualizaciones y abre el POS"
if (Test-Path $icono) { $lnk.IconLocation = "$icono,0" }
$lnk.Save()
Write-Host "Creado en el Escritorio: POS Uniformes"

# Limpieza: si existia el acceso viejo "Actualizar POS", se retira (todo
# vive ahora en el mismo acceso).
$viejo = Join-Path $desktop "Actualizar POS.lnk"
if (Test-Path $viejo) {
    Remove-Item $viejo -Force
    Write-Host "Retirado el acceso viejo: Actualizar POS"
}
