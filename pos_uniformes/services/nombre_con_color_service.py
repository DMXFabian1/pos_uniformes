"""El color va en el nombre cuando el producto tiene más de uno.

Ropa normal (Daniel, 2026-10-13): un producto es el MODELO y sus variantes son
talla × color. Mientras el color iba en el nombre del producto («Camisa Manga
Larga Borgoña») no hacía falta decirlo aparte; con un producto de varios
colores («Short Deportivo»: 7) la etiqueta, el ticket, la Libreta y el
carrito decían «Short Deportivo T: Unitalla» para los siete, y no había forma
de saber cuál se vendió o cuál se etiquetó.

La regla es UNA, y vive aquí: si el producto tiene más de un color (activo),
el nombre visible lleva el color de la variante. Si tiene uno solo, todo se
queda como estaba.
"""

from __future__ import annotations

from collections.abc import Iterable

#: Colores que no distinguen nada (no cuentan como «otro color»).
_SIN_COLOR = {"", "sin color", "-"}


def _norm(color: object) -> str:
    return " ".join(str(color or "").split()).casefold()


def es_multicolor(colores: Iterable[object]) -> bool:
    """¿Hay más de un color de verdad entre estas variantes?"""
    distintos = {_norm(c) for c in colores} - _SIN_COLOR
    return len(distintos) > 1


def nombre_con_color(nombre: str, color: object, *, multicolor: bool) -> str:
    """«Short Deportivo» + «Rojo» → «Short Deportivo Rojo» (solo si hace falta).

    No lo repite si el nombre ya lo trae (los productos viejos de un color por
    producto ya lo llevan en el nombre)."""
    nombre = str(nombre or "").strip()
    texto = " ".join(str(color or "").split())
    if not multicolor or _norm(texto) in _SIN_COLOR:
        return nombre
    if _norm(texto) in _norm(nombre):
        return nombre
    return f"{nombre} {texto}".strip()


def multicolor_de_producto(producto: object) -> bool:
    """Para objetos del ORM: mira las variantes activas del producto. Un
    producto armado a mano (pruebas, caché) puede traer `multicolor` ya puesto."""
    marcado = getattr(producto, "multicolor", None)
    if isinstance(marcado, bool):
        return marcado
    try:
        variantes = list(getattr(producto, "variantes", None) or [])
    except Exception:  # noqa: BLE001 — sin sesión no se adivina
        return False
    return es_multicolor(
        getattr(v, "color", "") for v in variantes if getattr(v, "activo", True)
    )


def multicolor_por_producto(filas: Iterable[dict]) -> dict[object, bool]:
    """Para el catálogo guardado (filas dict): {producto_id: multicolor}."""
    colores: dict[object, list] = {}
    for fila in filas:
        if not fila.get("variante_activo", True):
            continue
        colores.setdefault(fila.get("producto_id"), []).append(fila.get("color"))
    return {pid: es_multicolor(cs) for pid, cs in colores.items()}


def nombre_de_variante(variante: object, nombre: str) -> str:
    """`nombre` (como lo arma cada pantalla) + color si su producto lo pide."""
    producto = getattr(variante, "producto", None)
    return nombre_con_color(
        nombre, getattr(variante, "color", ""), multicolor=multicolor_de_producto(producto)
    )


def multicolor_en_filas(filas: Iterable[dict], producto_id: object) -> bool:
    """Para el catálogo guardado del kiosko: ¿ese producto tiene más de un color?"""
    if producto_id is None:
        return False
    return es_multicolor(
        f.get("color") for f in filas
        if f.get("producto_id") == producto_id and f.get("variante_activo", True)
    )
