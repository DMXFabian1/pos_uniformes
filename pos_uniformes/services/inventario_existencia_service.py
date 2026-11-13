"""Reglas puras de existencia para la pestaña Inventario.

Una sola cuenta para la tabla, los chips, los filtros y la ficha: la cifra
es el TOTAL de la presentación (`Variante.stock_actual` = tienda + bodega +
piso). Dónde está cada pieza se dice aparte (columnas Piso/Almacén).
"""

from __future__ import annotations

UMBRAL_BAJO = 3

VIRTUAL = "virtual"
AGOTADO = "agotado"
BAJO_MINIMO = "bajo_minimo"
BAJO = "bajo"
OK = "ok"


def clasificar_existencia(stock: int, *, stock_minimo: int | None = None) -> str:
    """virtual | agotado | bajo_minimo | bajo | ok, sobre el total."""
    if stock_minimo is not None and stock_minimo < 0:
        return VIRTUAL
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
    AGOTADO: "danger",
    BAJO_MINIMO: "warning",
    BAJO: "warning",
    OK: "positive",
}


def texto_existencia(stock: int, *, stock_minimo: int | None = None) -> str:
    """Texto de la columna «Stock»: «0 Agotado», «2 Bajo», «6 OK»…"""
    clase = clasificar_existencia(stock, stock_minimo=stock_minimo)
    if clase == VIRTUAL:
        return str(stock)
    return f"{stock} {_TEXTO[clase]}"


def tono_existencia(stock: int, *, stock_minimo: int | None = None) -> str:
    return _TONO[clasificar_existencia(stock, stock_minimo=stock_minimo)]
