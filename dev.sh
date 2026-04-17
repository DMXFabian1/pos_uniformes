#!/usr/bin/env bash
# ─────────────────────────────────────────────
#  dev.sh — levanta API + PWA en paralelo
#  Uso: ./dev.sh
#  Para detener: Ctrl+C (mata ambos procesos)
# ─────────────────────────────────────────────

ROOT="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$ROOT/pos_uniformes"
PWA_DIR="$ROOT/pwa"

# Colores
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

echo -e "\n${BOLD}╔══════════════════════════════════╗${RESET}"
echo -e "${BOLD}║   POS Uniformes — Dev Server     ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════╝${RESET}\n"

# Matar hijos al hacer Ctrl+C
cleanup() {
  echo -e "\n${YELLOW}Deteniendo servidores...${RESET}"
  kill "$API_PID" "$PWA_PID" 2>/dev/null
  wait "$API_PID" "$PWA_PID" 2>/dev/null
  echo -e "${GREEN}Listo.${RESET}\n"
  exit 0
}
trap cleanup INT TERM

# ── API (FastAPI + uvicorn) ──────────────────
echo -e "${CYAN}▶ Levantando API en :8000${RESET}"
# Buscar venv: primero en el worktree, luego en el proyecto original
if   [ -f "$API_DIR/.venv/bin/python3" ]; then
  VENV="$API_DIR/.venv/bin/python3"
elif [ -f "/Users/danielfabian/Documents/Playground 2/pos_uniformes/.venv/bin/python3" ]; then
  VENV="/Users/danielfabian/Documents/Playground 2/pos_uniformes/.venv/bin/python3"
else
  VENV="$(which python3)"
fi
cd "$API_DIR"
PYTHONPATH="$ROOT" "$VENV" api_server.py 2>&1 | sed "s/^/$(printf '\033[0;31m')[API]$(printf '\033[0m') /" &
API_PID=$!

# ── PWA (Vite HTTPS) ─────────────────────────
sleep 1   # darle un segundo a la API para arrancar primero
echo -e "${GREEN}▶ Levantando PWA en :5173 (HTTPS)${RESET}"
cd "$PWA_DIR"
npm run dev 2>&1 | sed "s/^/${GREEN}[PWA]${RESET} /" &
PWA_PID=$!

echo -e "\n${BOLD}Servidores corriendo. Ctrl+C para detener ambos.${RESET}\n"

# Esperar a que alguno termine inesperadamente
wait "$API_PID" "$PWA_PID"
