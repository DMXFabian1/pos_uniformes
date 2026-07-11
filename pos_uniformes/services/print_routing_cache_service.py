"""Cache local del *modo de impresión* de esta máquina (ajuste por PC).

Cada máquina decide si sus tickets se imprimen local o se envían al satélite:
  - MODO_LOCAL   : imprime en la impresora conectada a esta PC (comportamiento actual).
  - MODO_SATELITE: encola el ticket para que lo imprima la PC satélite.

Es un ajuste POR MÁQUINA, por eso vive en el cache local (satellite_data_dir),
no en la base compartida. `origen` etiqueta de dónde salió el trabajo
(p.ej. "principal" o "kiosko") para verlo luego en la GUI del despachador.

Default: MODO_LOCAL — sin configurar nada, el comportamiento no cambia.
"""

from __future__ import annotations

import json
from pathlib import Path

from pos_uniformes.utils.config import satellite_data_dir

MODO_LOCAL = "LOCAL"
MODO_SATELITE = "SATELITE"
_MODOS_VALIDOS = {MODO_LOCAL, MODO_SATELITE}
_DEFAULT_ORIGEN = "principal"

_CACHE_FILENAME = "print_routing.json"


def _cache_path() -> Path:
    return satellite_data_dir() / "data" / _CACHE_FILENAME


def save_print_routing(modo: str, origen: str = _DEFAULT_ORIGEN) -> None:
    if modo not in _MODOS_VALIDOS:
        raise ValueError(f"modo inválido: {modo!r} (usa MODO_LOCAL o MODO_SATELITE)")
    origen = (origen or _DEFAULT_ORIGEN).strip() or _DEFAULT_ORIGEN
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"modo": modo, "origen": origen}, ensure_ascii=False),
        encoding="utf-8",
    )


def load_print_routing() -> tuple[str, str]:
    """Devuelve (modo, origen). Ante ausencia o corrupción cae a (MODO_LOCAL, 'principal')."""
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
        modo = str(data.get("modo", MODO_LOCAL))
        if modo not in _MODOS_VALIDOS:
            modo = MODO_LOCAL
        origen = str(data.get("origen", _DEFAULT_ORIGEN)).strip() or _DEFAULT_ORIGEN
        return modo, origen
    except Exception:  # noqa: BLE001
        return MODO_LOCAL, _DEFAULT_ORIGEN


def enviar_al_satelite_activo() -> bool:
    """True si esta máquina está configurada para enviar sus tickets al satélite."""
    return load_print_routing()[0] == MODO_SATELITE
