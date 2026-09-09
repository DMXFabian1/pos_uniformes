#!/usr/bin/env bash
# Instalación del bot en un servidor Ubuntu/Debian recién creado. Idempotente: se puede repetir.
# Uso (como root o con sudo):  bash deploy/install.sh [URL_DEL_REPO] [RAMA]
set -euo pipefail

REPO_URL="${1:-}"
BRANCH="${2:-main}"
APP_USER="scalper"
APP_DIR="/opt/scalper"
SRC_DIR="$APP_DIR/src"

if [[ $EUID -ne 0 ]]; then echo "ejecuta como root: sudo bash deploy/install.sh ..."; exit 1; fi

echo "== paquetes del sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git rsync curl ca-certificates > /dev/null
timedatectl set-timezone UTC || true

echo "== usuario de servicio $APP_USER"
id -u "$APP_USER" > /dev/null 2>&1 || useradd --system --create-home --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$APP_DIR"

echo "== código"
if [[ -n "$REPO_URL" ]]; then
  if [[ -d "$SRC_DIR/.git" ]]; then
    git -C "$SRC_DIR" fetch --quiet origin "$BRANCH" && git -C "$SRC_DIR" checkout --quiet "$BRANCH" && git -C "$SRC_DIR" pull --quiet --ff-only origin "$BRANCH"
  else
    git clone --quiet --branch "$BRANCH" "$REPO_URL" "$SRC_DIR"
  fi
else
  # sin URL: se asume que este script corre desde una copia del proyecto
  HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  mkdir -p "$SRC_DIR"
  rsync -a --delete --exclude data --exclude .venv --exclude .git "$HERE/" "$SRC_DIR/"
fi
# el proyecto puede vivir en la raíz del repo o en la carpeta polymarket_scalper/
if [[ -f "$SRC_DIR/polymarket_scalper/pyproject.toml" ]]; then PROJ="$SRC_DIR/polymarket_scalper"; else PROJ="$SRC_DIR"; fi

echo "== entorno Python en $APP_DIR/venv"
[[ -d "$APP_DIR/venv" ]] || python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet -e "$PROJ[learn]"

echo "== configuración y datos"
mkdir -p "$APP_DIR/data"
[[ -f "$APP_DIR/config.yaml" ]] || cp "$PROJ/config.yaml" "$APP_DIR/config.yaml"
sed -i 's#^data_dir: .*#data_dir: /opt/scalper/data#' "$APP_DIR/config.yaml"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo "== servicios systemd"
install -m 644 "$PROJ/deploy/scalper-paper.service" /etc/systemd/system/scalper-paper.service
install -m 644 "$PROJ/deploy/scalper-dashboard.service" /etc/systemd/system/scalper-dashboard.service
systemctl daemon-reload
systemctl enable --now scalper-paper.service scalper-dashboard.service

echo
echo "listo. comandos útiles:"
echo "  systemctl status scalper-paper scalper-dashboard"
echo "  journalctl -u scalper-paper -f"
echo "  sudo -u $APP_USER $APP_DIR/venv/bin/scalper -c $APP_DIR/config.yaml report"
echo "  panel: ssh -L 8787:127.0.0.1:8787 usuario@servidor  y abrir http://127.0.0.1:8787"
