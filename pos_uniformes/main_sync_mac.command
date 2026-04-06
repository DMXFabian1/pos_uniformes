#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

find_python() {
  local candidate
  local names=(
    "$SCRIPT_DIR/.venv/bin/python"
    "python3.12"
    "python3.11"
    "python3.10"
    "python3"
  )

  for candidate in "${names[@]}"; do
    if [[ "$candidate" == */* ]]; then
      [[ -x "$candidate" ]] || continue
    else
      candidate="$(command -v "$candidate" 2>/dev/null || true)"
      [[ -n "$candidate" ]] || continue
    fi

    if "$candidate" - <<'PY' >/dev/null 2>&1
import tkinter as tk
root = tk.Tk()
root.withdraw()
root.destroy()
PY
    then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

PYTHON_BIN="$(find_python || true)"

if [[ -z "$PYTHON_BIN" ]]; then
  osascript -e 'display alert "Sincronizacion simple" message "No encontre un Python compatible con Tkinter. Instala Python 3.12+ o crea .venv en pos_uniformes." as critical'
  exit 1
fi

if [[ "${POS_SYNC_SELFTEST:-0}" == "1" ]]; then
  "$PYTHON_BIN" - <<'PY'
import tkinter as tk
from scripts.sync_checkpoint_gui import SyncCheckpointApp

root = tk.Tk()
root.withdraw()
SyncCheckpointApp(root)
root.update_idletasks()
root.destroy()
print("selftest: OK")
PY
  exit 0
fi

exec "$PYTHON_BIN" main_sync.py
