"""Reglas puras de existencia para la pestaña Inventario.

Una sola cuenta para la tabla, los chips, los filtros y la ficha: la cifra
es el TOTAL de la presentación (`Variante.stock_actual` = tienda + bodega +
piso). Dónde está cada pieza se dice aparte (columnas Piso/Almacén).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from pos_uniformes.services.conjunto_service import TIPOS_CONJUNTO

UMBRAL_BAJO = 3

VIRTUAL = "virtual"
NEGATIVO = "negativo"
AGOTADO = "agotado"
BAJO_MINIMO = "bajo_minimo"
BAJO = "bajo"
OK = "ok"


def es_conjunto_o_virtual(*, tipo_pieza_nombre: object = None, stock_minimo: int | None = None) -> bool:
    """Presentaciones cuyo stock no es mercancía propia sino armada de piezas.

    Criterio (el mismo que ya usa el sistema):
    - tipo de pieza en `conjunto_service.TIPOS_CONJUNTO` («Pants 3pz»,
      «Chamarra»): su stock lo calcula `sincronizar_conjunto` a partir del
      Pants 2pz / Playera / Pants Suelto, así que contarlo sería contar dos
      veces (es la misma lista que `conteo_service._TIPOS_VIRTUALES`);
    - o el marcador viejo `stock_minimo < 0` (la ficha ya lo llamaba «virtual»).
    """
    if stock_minimo is not None and stock_minimo < 0:
        return True
    return str(tipo_pieza_nombre or "").strip() in TIPOS_CONJUNTO


def es_fila_virtual(fila: Mapping[str, object]) -> bool:
    return es_conjunto_o_virtual(
        tipo_pieza_nombre=fila.get("tipo_pieza_nombre"),
        stock_minimo=_minimo(fila.get("stock_minimo")),
    )


def clasificar_existencia(stock: int, *, stock_minimo: int | None = None, virtual: bool = False) -> str:
    """virtual | negativo | agotado | bajo_minimo | bajo | ok, sobre el total.

    Un negativo (la venta del kiosko puede dejarlo) NO es «bajo»: es su
    propia clase, para que se vea y se corrija.
    """
    if virtual or (stock_minimo is not None and stock_minimo < 0):
        return VIRTUAL
    if stock < 0:
        return NEGATIVO
    if stock == 0:
        return AGOTADO
    if stock_minimo is not None and stock < stock_minimo:
        return BAJO_MINIMO
    if stock <= UMBRAL_BAJO:
        return BAJO
    return OK


_TEXTO = {
    AGOTADO: "Agotado",
    BAJO_MINIMO: "Bajo mín",
    BAJO: "Bajo",
    OK: "OK",
}

_TONO = {
    VIRTUAL: "neutral",
    NEGATIVO: "danger",
    AGOTADO: "danger",
    BAJO_MINIMO: "warning",
    BAJO: "warning",
    OK: "positive",
}


def texto_existencia(stock: int, *, stock_minimo: int | None = None, virtual: bool = False) -> str:
    """Texto de la columna «Stock»: «0 Agotado», «2 Bajo», «6 OK», «3 Conjunto»…"""
    clase = clasificar_existencia(stock, stock_minimo=stock_minimo, virtual=virtual)
    if clase == VIRTUAL:
        return f"{stock} Conjunto"
    if clase == NEGATIVO:
        return f"\u2212{abs(stock)} Negativo"
    return f"{stock} {_TEXTO[clase]}"


def tono_existencia(stock: int, *, stock_minimo: int | None = None, virtual: bool = False) -> str:
    return _TONO[clasificar_existencia(stock, stock_minimo=stock_minimo, virtual=virtual)]


@dataclass(frozen=True)
class ConteoExistencias:
    negativos: int
    agotados: int
    bajos: int
    piezas: int  # suma de existencias sin conjuntos/virtuales


def contar_existencias(filas: Iterable[Mapping[str, object]]) -> ConteoExistencias:
    """Cuenta para los chips. «Bajo» incluye «bajo mínimo»; un negativo no.

    Los conjuntos/virtuales no entran (ver `es_conjunto_o_virtual`).
    """
    negativos = agotados = bajos = piezas = 0
    for fila in filas:
        if es_fila_virtual(fila):
            continue
        stock = int(fila["stock_actual"])
        piezas += stock
        clase = clasificar_existencia(stock, stock_minimo=_minimo(fila.get("stock_minimo")))
        if clase == NEGATIVO:
            negativos += 1
        elif clase == AGOTADO:
            agotados += 1
        elif clase in (BAJO, BAJO_MINIMO):
            bajos += 1
    return ConteoExistencias(negativos=negativos, agotados=agotados, bajos=bajos, piezas=piezas)


def coincide_filtro_existencia(
    stock: int, filtro: str, *, stock_minimo: int | None = None, virtual: bool = False
) -> bool:
    """Filtro «Stock» de Inventario: negative | zero | low | available | below_min.

    Un conjunto/virtual solo aparece sin filtro o en «Disponible» (como antes
    con `stock_minimo < 0`).
    """
    if not filtro:
        return True
    clase = clasificar_existencia(stock, stock_minimo=stock_minimo, virtual=virtual)
    if clase == VIRTUAL:
        return filtro == "available"
    if filtro == "negative":
        return clase == NEGATIVO
    if filtro == "zero":
        return clase == AGOTADO
    if filtro == "low":
        return clase in (BAJO, BAJO_MINIMO)
    if filtro == "available":
        return stock > 0
    if filtro == "below_min":
        return stock_minimo is not None and 0 <= stock < stock_minimo
    return True


def _minimo(valor: object) -> int | None:
    return int(valor) if valor is not None else None  # type: ignore[arg-type]
