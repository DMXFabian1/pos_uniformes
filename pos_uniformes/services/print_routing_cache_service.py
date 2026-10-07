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
_TIPOS_CONOCIDOS = ("TICKET", "CORTE", "ETIQUETA", "CONTEO", "PEDIDO")


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


def guardar_impresoras(origen: str, tipos) -> None:
    """Guarda QUÉ IMPRESORAS tiene esta PC. Es el ajuste de verdad.

    De aquí salen las dos respuestas que antes pedían dos interruptores: lo que
    esta PC imprime de LO SUYO y lo que atiende de la cola de los demás. Una PC
    que no tiene ninguna impresora es lo que antes se llamaba "Estación".

    El modelo viejo era un interruptor por máquina —todo aquí o todo allá— y
    dejó de describir la tienda el día que la PC principal estrenó impresora de
    tickets sin tener las Brother de etiquetas: en Estación sus tickets se iban
    al kiosko teniendo la impresora buena enfrente, y en Servidor sus etiquetas
    salían a una etiquetadora que no existe (Daniel, 2026-10-07).

    Se sigue escribiendo `modo` aunque ya no mande: una PC con un build viejo
    lee el mismo archivo y tiene que seguir entendiéndolo.
    """
    limpios = _limpiar_tipos(tipos) or []
    modo = MODO_LOCAL if limpios else MODO_SATELITE
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"modo": modo, "origen": (origen or _DEFAULT_ORIGEN).strip() or _DEFAULT_ORIGEN,
             "tipos": limpios},
            ensure_ascii=False,
        ),
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


def tipos_configurados() -> list[str] | None:
    """Lo que dice el archivo, tal cual. None = no se ha configurado nunca."""
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if "tipos" not in data:
        return None
    return _limpiar_tipos(data.get("tipos")) or []


def impresoras_de_esta_pc() -> list[str]:
    """Qué sabe imprimir esta PC, SIEMPRE como lista concreta.

    Si nunca se configuró, se deduce del interruptor viejo para que ninguna
    máquina cambie de comportamiento por actualizarse: lo que era Servidor
    imprime todo, lo que era Estación no imprime nada.
    """
    guardado = tipos_configurados()
    if guardado is not None:
        return guardado
    modo, _origen = load_print_routing()
    return list(_TIPOS_CONOCIDOS) if modo == MODO_LOCAL else []


def puede_imprimir(tipo) -> bool:
    """¿Esta PC tiene cómo imprimir eso? Decide si lo suyo sale aquí o se encola."""
    nombre = str(getattr(tipo, "value", tipo) or "").strip().upper()
    return nombre in impresoras_de_esta_pc()


def tipos_que_atiende():
    """Los `TipoTrabajo` que esta PC despacha de la cola, o None = todos.

    None significa "todos" y no "ninguno": es lo que espera el despachador
    cuando no hay filtro."""
    nombres = impresoras_de_esta_pc()
    if not nombres:
        return []
    if set(nombres) >= set(_TIPOS_CONOCIDOS):
        return None
    from pos_uniformes.database.models import TipoTrabajo

    return [t for t in TipoTrabajo if t.value in nombres]


def enviar_al_satelite_activo() -> bool:
    """True si esta máquina no imprime NADA aquí (lo que antes era Estación)."""
    return not impresoras_de_esta_pc()
