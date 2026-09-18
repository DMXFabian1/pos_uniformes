"""El nombre de la persona donde el sistema guarda su código.

Los registros (cortes, pagos, movimientos, conteos, la Libreta) guardan
`VEND-1`, `ENC-1`… porque con eso se decide quién puede qué. Pero en pantalla,
en los tickets y en Telegram va el nombre (Daniel, 2026-09-18: "necesito que
siempre aparezca el nombre de la persona, no VEND-1 y así").

    nombres = nombres_por_codigo(session)      # {"VEND-1": "Daniel Fabian", ...}
    mostrar("VEND-1", nombres)                 # "Daniel Fabian"
    mostrar("Ana López (VEND-3)", nombres)     # "Ana López"  (ya traía el nombre)
    mostrar("admin (satélite)", nombres)       # sin cambios: no es un código

El mapa se cachea 5 min y se guarda en `data/empleadas_nombres.json` para
que el kiosko lo tenga aun sin la PC principal.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

_CODIGO = re.compile(r"\b([A-Z]{2,6}-\d{1,4})\b")
_TTL_SEG = 300

_cache: dict[str, str] = {}
_cache_en: float = 0.0


def _ruta_local() -> Path:
    from pos_uniformes.utils.config import satellite_data_dir

    return satellite_data_dir() / "data" / "empleadas_nombres.json"


def _guardar_local(nombres: dict[str, str]) -> None:
    try:
        p = _ruta_local()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(nombres, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:  # noqa: BLE001 — la copia local es un extra
        pass


def _leer_local() -> dict[str, str]:
    try:
        data = json.loads(_ruta_local().read_text(encoding="utf-8"))
        return {str(k).upper(): str(v) for k, v in data.items() if v}
    except Exception:  # noqa: BLE001
        return {}


def invalidar() -> None:
    """Después de dar de alta o renombrar a alguien."""
    global _cache_en
    _cache_en = 0.0


def nombres_por_codigo(session=None) -> dict[str, str]:
    """{código: nombre completo} de todas las empleadas (activas o no: los
    registros viejos siguen siendo de alguien). Sin sesión, o sin base, lo
    que haya en caché o en la copia local."""
    global _cache, _cache_en
    if _cache and time.monotonic() - _cache_en < _TTL_SEG:
        return _cache
    if session is not None:
        try:
            from sqlalchemy import select

            from pos_uniformes.database.models import Empleada

            filas = session.execute(select(Empleada.codigo, Empleada.nombre_completo)).all()
            nombres = {str(c).strip().upper(): str(n).strip() for c, n in filas if c and n and str(n).strip()}
            if nombres:
                _cache, _cache_en = nombres, time.monotonic()
                _guardar_local(nombres)
                return _cache
        except Exception:  # noqa: BLE001 — sin base se usa lo que haya
            pass
    if _cache:
        return _cache
    _cache = _leer_local()
    _cache_en = time.monotonic() if _cache else 0.0
    return _cache


def mostrar(texto: object, nombres: dict[str, str] | None = None, *, corto: bool = False) -> str:
    """Cambia cada código por el nombre. Si el texto ya trae el nombre y el
    código entre paréntesis ("Ana López (VEND-3)"), se queda solo el nombre.
    `corto`: solo el primer nombre ("Daniel"), venga del código o ya escrito."""
    s = str(texto or "")
    if not s:
        return s
    nombres = nombres if nombres is not None else nombres_por_codigo()

    def _nombre(code: str) -> str:
        return nombres.get(code.upper(), code)

    def _reemplazo(m: re.Match) -> str:
        code = m.group(1)
        if code.upper() not in nombres:
            return code
        antes = s[: m.start()].rstrip()
        if antes.endswith("("):
            # "Ana López (VEND-3)" → el nombre ya está antes: fuera el paréntesis
            return code
        return _nombre(code)

    out = _CODIGO.sub(_reemplazo, s)
    # Quitar "(VEND-3)" cuando delante ya hay un nombre.
    out = re.sub(r"(\S)\s*\(([A-Z]{2,6}-\d{1,4})\)", lambda m: m.group(1) if m.group(2).upper() in nombres else m.group(0), out)
    if corto:
        return out.split()[0] if out.strip() else out
    return out


def nombre_de(code: object, session=None, *, corto: bool = False) -> str:
    """El nombre de un código; el código mismo si no se conoce."""
    return mostrar(code, nombres_por_codigo(session), corto=corto)
