"""¿Por qué el contador de afluencia no cuenta? Deja reporte en reportes/afluencia.txt.

Revisa, en orden, todo lo que tiene que estar bien para que la tabla
`afluencia_hora` se llene, y dice claramente qué falla:

  1. el entorno propio del contador (afluencia/.venv) y sus paquetes
  2. la configuración del DVR (data/dvr_settings.json o el env) y afluencia.json
  3. que cada cámara abra por RTSP y entregue un cuadro
  4. que Postgres responda y la tabla exista, y cuántas filas tiene
  5. la tarea de Windows "POS Afluencia": si existe y si va oculta
  6. las últimas líneas de logs/afluencia.log

Uso: afluencia\\diagnostico_afluencia.bat   (luego scripts\\enviar_reporte.bat)
Corre con el Python del POS; para probar las cámaras usa el del contador.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
REPORTE = RAIZ / "reportes" / "afluencia.txt"
VENV_PY = AQUI / ".venv" / ("Scripts/python.exe" if platform.system() == "Windows" else "bin/python")


def _l(f, texto: str = "") -> None:
    print(texto)
    f.write(texto + "\n")


def _correr(cmd: list[str], timeout: int = 90) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(AQUI))
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return -1, f"(no se pudo ejecutar: {exc})"


def main() -> int:
    REPORTE.parent.mkdir(parents=True, exist_ok=True)
    with REPORTE.open("w", encoding="utf-8") as f:
        _l(f, f"=== Diagnóstico de afluencia · {datetime.now():%d/%m/%Y %H:%M} · {platform.node()} ===")

        _l(f, "\n--- 1. Entorno del contador ---")
        if not VENV_PY.exists():
            _l(f, f"NO existe {VENV_PY}. Nunca se instaló: corre afluencia\\instalar_afluencia.bat")
        else:
            code, out = _correr([str(VENV_PY), "-c", "import cv2, ultralytics, psycopg; print('cv2', cv2.__version__, '| ultralytics', ultralytics.__version__)"], 60)
            _l(f, "paquetes: " + (out.strip().splitlines()[-1] if out.strip() else "(sin salida)"))
            if code != 0:
                _l(f, "-> Faltan paquetes o están rotos. Vuelve a correr instalar_afluencia.bat")
        _l(f, f"modelo yolov8n.pt: {'presente' if (AQUI / 'yolov8n.pt').exists() else 'NO está (se descarga en la primera corrida; necesita internet)'}")

        _l(f, "\n--- 2. Configuración ---")
        cfg = AQUI / "afluencia.json"
        if cfg.exists():
            try:
                data = json.loads(cfg.read_text(encoding="utf-8"))
                cams = data.get("camaras", [])
                _l(f, f"afluencia.json: {len(cams)} cámaras → " + ", ".join(f"{c.get('nombre')} (canal {c.get('canal')}, {c.get('modo')})" for c in cams))
            except Exception as exc:  # noqa: BLE001
                _l(f, f"afluencia.json ILEGIBLE: {exc}")
        else:
            _l(f, "NO existe afluencia.json (el instalador lo copia del ejemplo)")
        dvr = RAIZ / "data" / "dvr_settings.json"
        env_dvr = os.environ.get("POS_UNIFORMES_DVR_HOST") or ""
        if dvr.exists():
            try:
                d = json.loads(dvr.read_text(encoding="utf-8"))
                _l(f, f"DVR (data/dvr_settings.json): host={d.get('host')} rtsp={d.get('rtsp_port', 554)} usuario={d.get('user') or d.get('usuario')}")
            except Exception as exc:  # noqa: BLE001
                _l(f, f"dvr_settings.json ILEGIBLE: {exc}")
        elif env_dvr:
            _l(f, f"DVR (env): host={env_dvr}")
        else:
            _l(f, "NO hay configuración del DVR: en el kiosko, Ctrl+Shift+A → Cámaras → Guardar (crea data/dvr_settings.json)")

        _l(f, "\n--- 3. Cámaras por RTSP (calibración) ---")
        if VENV_PY.exists():
            code, out = _correr([str(VENV_PY), "contador_afluencia.py", "--calibrar"], 120)
            lineas = [x for x in out.splitlines() if "calibraci" in x.lower() or "error" in x.lower() or "no se pudo" in x.lower() or "falta" in x.lower()]
            _l(f, "\n".join(lineas) if lineas else out.strip()[-800:])
            _l(f, "-> " + ("las cámaras abren; revisa calibracion\\*.jpg" if code == 0 else "ALGO FALLÓ abriendo las cámaras (arriba dice cuál)"))
        else:
            _l(f, "(sin entorno: no se probaron)")

        _l(f, "\n--- 4. Base de datos ---")
        try:
            sys.path.insert(0, str(RAIZ.parent))
            from pos_uniformes.database.connection import engine, get_session
            from sqlalchemy import text

            with get_session() as s:
                n, ult = s.execute(text("select count(*), max(updated_at) from afluencia_hora")).one()
            _l(f, f"Postgres {engine.url.host}: responde · afluencia_hora tiene {n} filas · última escritura: {ult or 'nunca'}")
        except Exception as exc:  # noqa: BLE001
            _l(f, f"Postgres NO responde o falta la tabla: {str(exc)[:160]}")

        _l(f, "\n--- 5. Tarea de Windows ---")
        if platform.system() == "Windows":
            code, out = _correr(["schtasks", "/Query", "/TN", "POS Afluencia", "/V", "/FO", "LIST"], 30)
            if code != 0:
                _l(f, 'NO existe la tarea "POS Afluencia": corre afluencia\\instalar_afluencia.bat (o actualiza la PC: la postactualización la crea si hay .venv)')
            else:
                oculta = "correr_oculto.vbs" in out
                estado = next((x.strip() for x in out.splitlines() if "Estado" in x or "Status" in x), "")
                _l(f, f"existe · {'OCULTA (bien)' if oculta else 'VISIBLE: abre consola; actualiza la PC para que quede oculta'} · {estado}")
            code, out = _correr(["tasklist", "/FI", "IMAGENAME eq python.exe", "/V"], 30)
            vivo = "contador_afluencia" in out
            _l(f, f"proceso corriendo ahora: {'sí' if vivo else 'NO (nadie está contando)'}")
        else:
            _l(f, "(no es Windows)")

        _l(f, "\n--- 6. Últimas líneas de logs/afluencia.log ---")
        log = RAIZ / "logs" / "afluencia.log"
        if log.exists():
            _l(f, "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]))
        else:
            _l(f, "no hay log todavía (el contador nunca arrancó con esta versión)")
    print(f"\nReporte guardado en {REPORTE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
