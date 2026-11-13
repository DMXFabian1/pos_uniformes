"""Qué precios bajan en un cambio de precio en lote (Inventario, tanda 5).

Regla de oro de la tienda: **nunca bajar precios** salvo que el dueño lo
marque. Decisión de Daniel (2026-11-13): no se bloquea; antes de aplicar se
avisa en rojo «SKU · talla: baja de $X a $Y» y se pide confirmar, con
Cancelar por defecto. Si nada baja, el flujo queda igual que antes.

Puro: recibe los pares (variante_id, precio nuevo) del diálogo y las filas
con su `precio_venta`. Ese precio NO debe salir del snapshot de la pestaña
(puede tener horas): `leer_precios_actuales` lo lee de la base en una sola
consulta justo antes de avisar, y `filas_con_precio_de_base` lo pone sobre
las filas y dice cuáles cambiaron desde la última recarga. Así una bajada
real (la base ya estaba más arriba) nunca se aplica sin aviso.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping

from pos_uniformes.services.rebaja_service import fmt_corto

#: Cuántos renglones enseña el aviso antes de resumir «… y N más».
MAXIMO_RENGLONES = 8

_CENTAVO = Decimal("0.01")


def _dinero(valor: object) -> Decimal | None:
    if valor in (None, ""):
        return None
    try:
        return Decimal(str(valor)).quantize(_CENTAVO)
    except (InvalidOperation, ValueError):
        return None


@dataclass(frozen=True)
class BajaDePrecio:
    variante_id: int
    sku: str
    talla: str
    prenda: str
    antes: Decimal
    despues: Decimal

    def texto(self) -> str:
        talla = f" · talla {self.talla}" if self.talla else ""
        return f"{self.sku}{talla}: baja de {fmt_corto(self.antes)} a {fmt_corto(self.despues)}"


def leer_precios_actuales(session, variante_ids: Iterable[object]) -> dict[int, dict[str, object]]:
    """El precio de cada variante del lote como está en la base AHORA (una consulta).

    Devuelve {variante_id: {"variante_id", "sku", "talla", "precio_venta", "producto_nombre"}}.
    """
    from sqlalchemy import select

    from pos_uniformes.database.models import Producto, Variante

    ids = sorted({int(i) for i in variante_ids})  # type: ignore[arg-type]
    if not ids:
        return {}
    consulta = (
        select(Variante.id, Variante.sku, Variante.talla, Variante.precio_venta, Producto.nombre)
        .join(Producto, Producto.id == Variante.producto_id)
        .where(Variante.id.in_(ids))
    )
    salida: dict[int, dict[str, object]] = {}
    for variante_id, sku, talla, precio, nombre in session.execute(consulta).all():
        salida[int(variante_id)] = {
            "variante_id": int(variante_id),
            "sku": sku,
            "talla": talla,
            "precio_venta": precio,
            "producto_nombre": nombre,
        }
    return salida


def filas_con_precio_de_base(
    filas: Iterable[Mapping[str, object]], de_base: Mapping[int, Mapping[str, object]]
) -> tuple[list[dict[str, object]], list[int]]:
    """Las filas con el `precio_venta` de la base; y los ids cuyo precio cambió desde el snapshot.

    Una variante del lote que no esté en el snapshot entra con los datos de la
    base. Sin dato de la base (no se pudo leer) la fila queda como venía.
    """
    salida: list[dict[str, object]] = []
    cambiaron: list[int] = []
    vistos: set[int] = set()
    for fila in filas:
        copia = dict(fila)
        try:
            variante_id = int(fila.get("variante_id"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            salida.append(copia)
            continue
        vistos.add(variante_id)
        base = de_base.get(variante_id)
        if base is not None and _dinero(base.get("precio_venta")) is not None:
            if _dinero(base.get("precio_venta")) != _dinero(fila.get("precio_venta")):
                cambiaron.append(variante_id)
            copia["precio_venta"] = base.get("precio_venta")
        salida.append(copia)
    for variante_id, base in de_base.items():
        if int(variante_id) not in vistos:
            salida.append(dict(base))
    return salida, cambiaron


def precios_que_bajan(
    items: Iterable[tuple[int, object]], filas: Iterable[Mapping[str, object]]
) -> list[BajaDePrecio]:
    """Las tallas cuyo precio nuevo queda por debajo del actual, en el orden del lote."""
    por_id: dict[int, Mapping[str, object]] = {}
    for fila in filas:
        try:
            por_id[int(fila.get("variante_id"))] = fila  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
    bajas: list[BajaDePrecio] = []
    for variante_id, nuevo in items:
        fila = por_id.get(int(variante_id))
        if fila is None:
            continue
        antes, despues = _dinero(fila.get("precio_venta")), _dinero(nuevo)
        if antes is None or despues is None or despues >= antes:
            continue
        bajas.append(
            BajaDePrecio(
                variante_id=int(variante_id),
                sku=str(fila.get("sku") or ""),
                talla=str(fila.get("talla") or ""),
                prenda=str(fila.get("producto_nombre_base") or fila.get("producto_nombre") or ""),
                antes=antes,
                despues=despues,
            )
        )
    return bajas


def titulo_bajas(cuantas: int) -> str:
    return "1 precio baja" if cuantas == 1 else f"{cuantas:,} precios bajan"


def renglones_bajas(bajas: list[BajaDePrecio], *, maximo: int = MAXIMO_RENGLONES) -> list[str]:
    """«SKU · talla: baja de $X a $Y», resumido con «… y N más» si son muchas."""
    renglones = [baja.texto() for baja in bajas[:maximo]]
    resto = len(bajas) - maximo
    if resto > 0:
        renglones.append(f"… y {resto:,} más")
    return renglones
