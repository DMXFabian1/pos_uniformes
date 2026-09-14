#!/usr/bin/env bash
# Corrida larga de la fase de pata suelta, en macOS o Linux.
#
#   ./correr.sh                 corrida congelada de 8 horas
#   ./correr.sh --horas 4       otra duración
#   ./correr.sh --informe       solo los informes de lo ya capturado, sin correr nada
#   ./correr.sh --sin-pull      no traer cambios del repositorio
#
# Hay que EJECUTARLO, no pegar su contenido en la terminal: se apoya en saber dónde vive.
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$RAIZ" || exit 1

HORAS=8
PULL=1
SOLO_INFORME=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --horas)    HORAS="$2"; shift 2 ;;
    --informe)  SOLO_INFORME=1; shift ;;
    --sin-pull) PULL=0; shift ;;
    -h|--help)  sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "opción desconocida: $1"; exit 1 ;;
  esac
done

rojo()  { printf '\033[31m%s\033[0m\n' "$*"; }
verde() { printf '\033[32m%s\033[0m\n' "$*"; }
gris()  { printf '\033[90m%s\033[0m\n' "$*"; }
paso()  { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }

if [[ ! -f "$RAIZ/config.yaml" ]]; then
  rojo "No encuentro config.yaml junto a este script."
  rojo "Esto hay que EJECUTARLO, no pegarlo en la terminal:"
  echo  "    cd ruta/al/repo/polymarket_scalper && ./correr.sh"
  exit 1
fi

# ---------------------------------------------------------------- 1. Python
paso "Python"
PY=""
for cand in python3.13 python3.12 python3.11 python3; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
    PY="$cand"; break
  fi
done
if [[ -z "$PY" ]]; then
  rojo "Hace falta Python 3.11 o más nuevo (el que trae macOS de fábrica es más viejo)."
  echo  "    brew install python@3.12"
  exit 1
fi
verde "$($PY --version) en $(command -v $PY)"

# ---------------------------------------------------------------- 2. repositorio
if [[ $PULL -eq 1 ]]; then
  paso "Traer cambios"
  git pull --ff-only || { rojo "El pull no fue limpio. Resuélvelo y vuelve a intentarlo."; exit 1; }
fi

# ---------------------------------------------------------------- 3. entorno
paso "Entorno"
if [[ ! -d .venv ]]; then
  gris "creando .venv (la primera vez tarda un par de minutos)"
  "$PY" -m venv .venv || exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -e ".[dev,learn]" || { rojo "Falló la instalación de dependencias."; exit 1; }
verde "listo"

if [[ $SOLO_INFORME -eq 1 ]]; then
  paso "Informes"
  scalper calidad || true
  scalper patas
  scalper validacion
  exit 0
fi

# ---------------------------------------------------------------- 4. tests
paso "Tests"
if ! python -m pytest tests/ -q; then
  rojo "Hay tests en rojo. No se arranca una corrida de medición con el código roto."
  exit 1
fi

# ---------------------------------------------------------------- 5. árbol limpio
# La corrida congelada se niega a arrancar con cambios sin comprometer, porque entonces el commit
# no describe el código que va a correr y el experimento no sería reproducible.
paso "Árbol de trabajo"
if [[ -n "$(git status --porcelain)" ]]; then
  rojo "Hay cambios sin comprometer. La corrida congelada no puede arrancar así:"
  git status --short
  echo
  echo "Compromételos, o descártalos con:  git checkout -- ."
  exit 1
fi
verde "limpio · commit $(git rev-parse --short HEAD)"

# ---------------------------------------------------------------- 6. respaldo
paso "Respaldo antes de empezar"
python respaldo.py crear || gris "(no había datos que copiar todavía)"

# ---------------------------------------------------------------- 7. corrida
SEGUNDOS=$(python -c "print(int(float('$HORAS') * 3600))")
RUN="patas-$(date +%Y%m%d-%H%M)"
paso "Corrida congelada · $HORAS h · run_id $RUN"
gris "El Mac no se dormirá mientras corre (caffeinate). La pantalla sí puede apagarse."
gris "Para pararla: Ctrl+C. Lo capturado hasta ese momento se guarda."
echo

mkdir -p logs
scalper --log-file "logs/$RUN.log" paper --duration "$SEGUNDOS" --run-id "$RUN"
SALIDA=$?

# ---------------------------------------------------------------- 8. ¿vale la corrida?
paso "¿Vale esta corrida?"
if ! scalper calidad --run-id "$RUN"; then
  rojo "La corrida NO pasa las comprobaciones de calidad."
  rojo "No mires el informe todavía: el dato no es fiable. Pega esto en el chat."
  exit 1
fi
verde "el dato es válido"

# ---------------------------------------------------------------- 9. informes
paso "Qué dice"
scalper patas

paso "Respaldo final"
python respaldo.py crear

echo
verde "Terminado. run_id: $RUN   ·   log: logs/$RUN.log"
gris "Para volver a ver los informes sin correr nada:  ./correr.sh --informe"
exit $SALIDA
