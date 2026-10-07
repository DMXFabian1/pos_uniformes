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


#: Qué tipos de trabajo atiende esta PC. `None` = todos, que es como se
#: comportó siempre y sigue siendo lo correcto cuando hay UN solo servidor.
#: Existe desde que hay dos: la principal estrenó impresora de tickets pero las
#: Brother de etiquetas siguen en el kiosko, y sin esto la principal reclamaría
#: etiquetas para mandarlas a una impresora que no tiene y las dejaría en ERROR
#: (Daniel, 2026-10-07). Se guardan por NOMBRE, no por el enum, para que un
#: tipo nuevo no rompa el archivo de una máquina vieja.
_TIPOS_CONOCIDOS = ("TICKET", "ETIQUETA", "CONTEO", "PEDIDO")


def _limpiar_tipos(tipos) -> list[str] | None:
    if tipos is None:
        return None
    limpios = [
        str(t).strip().upper() for t in tipos
        if str(t).strip().upper() in _TIPOS_CONOCIDOS
    ]
    # Lista vacía = "no atiendo nada", que no es un estado útil: sería un
    # servidor que no sirve. Se trata como "todos", igual que ausente.
    return sorted(set(limpios)) or None


def save_print_routing(modo: str, origen: str = _DEFAULT_ORIGEN, tipos=None) -> None:
    if modo not in _MODOS_VALIDOS:
        raise ValueError(f"modo inválido: {modo!r} (usa MODO_LOCAL o MODO_SATELITE)")
    origen = (origen or _DEFAULT_ORIGEN).strip() or _DEFAULT_ORIGEN
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    datos = {"modo": modo, "origen": origen}
    limpios = _limpiar_tipos(tipos)
    if limpios is not None:
        datos["tipos"] = limpios
    path.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")


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


def tipos_configurados() -> list[str] | None:
    """Los nombres de los tipos que atiende esta PC, o None = todos."""
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return _limpiar_tipos(data.get("tipos"))


def tipos_que_atiende():
    """Los `TipoTrabajo` que esta PC despacha, o None = todos.

    None y "todos" son lo mismo a propósito: una máquina que nunca configuró
    nada tiene que seguir comportándose como antes."""
    nombres = tipos_configurados()
    if nombres is None:
        return None
    from pos_uniformes.database.models import TipoTrabajo

    tipos = [t for t in TipoTrabajo if t.value in nombres]
    return tipos or None


def enviar_al_satelite_activo() -> bool:
    """True si esta máquina está configurada para enviar sus tickets al satélite."""
    return load_print_routing()[0] == MODO_SATELITE
