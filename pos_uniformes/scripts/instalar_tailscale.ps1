#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Pone Tailscale en la PC principal para llegar a la tienda desde cualquier red
    (Daniel, 2026-10-26: «hacer cortes y ver las ventas desde otro sitio»).

    Instala Tailscale (winget), lo levanta con nombre «pos-principal», se asegura
    de que el firewall deje pasar Postgres (5432) y la PWA (8000) desde la red de
    Tailscale (100.64.0.0/10), y al final imprime la IP 100.x.x.x que hay que
    poner en la Mac y en el celular.

.PARAMETER AuthKey
    Opcional. Llave de https://login.tailscale.com/admin/settings/keys para no
    tener que iniciar sesión en el navegador (útil si lo corre otra persona).
#>
param([string]$AuthKey = "")

$ErrorActionPreference = "Stop"
function Paso { param($m) Write-Host "`n== $m ==" -ForegroundColor Cyan }
function Ok   { param($m) Write-Host "  OK  $m" -ForegroundColor Green }

Paso "1/4 Tailscale instalado?"
$exe = "C:\Program Files\Tailscale\tailscale.exe"
if (-not (Test-Path $exe)) {
    winget install --id Tailscale.Tailscale -e --silent --accept-package-agreements --accept-source-agreements
    if (-not (Test-Path $exe)) { throw "No se instaló Tailscale. Bájalo de https://tailscale.com/download/windows y vuelve a correr esto." }
    Ok "Instalado."
} else { Ok "Ya estaba." }

Paso "2/4 Conectando (nombre: pos-principal)"
$args = @("up", "--hostname=pos-principal", "--accept-dns=false")
if ($AuthKey) { $args += "--auth-key=$AuthKey" }
else { Write-Host "  Si pide iniciar sesión, se abre el navegador: entra con la cuenta de Google de Daniel." -ForegroundColor Yellow }
& $exe @args
Ok "Conectado."

Paso "3/4 Firewall: Postgres y PWA desde la red de Tailscale"
foreach ($r in @(@{n="POS Postgres por Tailscale"; p=5432}, @{n="POS PWA por Tailscale"; p=8000})) {
    if (-not (Get-NetFirewallRule -DisplayName $r.n -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $r.n -Direction Inbound -Protocol TCP -LocalPort $r.p -RemoteAddress 100.64.0.0/10 -Action Allow | Out-Null
        Ok "Regla '$($r.n)' creada."
    } else { Ok "Regla '$($r.n)' ya existía." }
}

Paso "4/4 La IP de esta PC en Tailscale"
$ip = (& $exe ip -4).Trim()
Write-Host ""
Write-Host "  ==========================================" -ForegroundColor Green
Write-Host "   PC principal en Tailscale: $ip" -ForegroundColor Green
Write-Host "   Celular:  http://${ip}:8000/app" -ForegroundColor Green
Write-Host "   Mac:      scripts/mac_tienda.sh remota $ip" -ForegroundColor Green
Write-Host "  ==========================================" -ForegroundColor Green
if (-not (Test-Path "reportes")) { New-Item -ItemType Directory reportes | Out-Null }
"$ip" | Set-Content "reportes\tailscale_ip.txt"
