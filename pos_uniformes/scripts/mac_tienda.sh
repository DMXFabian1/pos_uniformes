#!/bin/zsh
# La Mac apunta a la tienda por la LAN (192.168.0.10) o por Tailscale (100.x).
#   scripts/mac_tienda.sh remota 100.64.1.2   # de viaje: guarda la IP y la usa
#   scripts/mac_tienda.sh remota              # de viaje: usa la IP guardada
#   scripts/mac_tienda.sh local               # en la tienda
#   scripts/mac_tienda.sh                     # dice cómo está y si responde
set -e
cd "$(dirname "$0")/.."
ENV=pos_uniformes.env
LAN=192.168.0.10
guardada=$(grep -E '^# TAILSCALE_TIENDA=' "$ENV" | cut -d= -f2)
actual=$(grep -E '^POS_UNIFORMES_DB_HOST=' "$ENV" | cut -d= -f2)

poner() {
  sed -i '' -E "s/^(POS_UNIFORMES_(SERVER|DB)_HOST=).*/\1$1/" "$ENV"
  echo "La Mac apunta a $1 ($2)."
}
prueba() {
  /usr/bin/python3 - "$1" <<'PY'
import socket, sys
h = sys.argv[1]
try:
    socket.create_connection((h, 5432), timeout=3).close(); print(f"Postgres responde en {h}.")
except OSError as e:
    print(f"Postgres NO responde en {h}: {e}")
PY
}

case "${1:-}" in
  remota)
    ip="${2:-$guardada}"
    [[ -z "$ip" ]] && { echo "Falta la IP de Tailscale de la principal (está en reportes\\tailscale_ip.txt de la PC)."; exit 1; }
    grep -q '^# TAILSCALE_TIENDA=' "$ENV" && sed -i '' -E "s/^# TAILSCALE_TIENDA=.*/# TAILSCALE_TIENDA=$ip/" "$ENV" || echo "# TAILSCALE_TIENDA=$ip" >> "$ENV"
    poner "$ip" "Tailscale"; prueba "$ip" ;;
  local)
    poner "$LAN" "red de la tienda"; prueba "$LAN" ;;
  *)
    echo "Ahora: $actual  (Tailscale guardada: ${guardada:-ninguna})"; prueba "$actual" ;;
esac
