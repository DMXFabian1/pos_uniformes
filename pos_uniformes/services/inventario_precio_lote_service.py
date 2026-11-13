"""Qué precios bajan en un cambio de precio en lote (Inventario, tanda 5).

Regla de oro de la tienda: **nunca bajar precios** salvo que el dueño lo
marque. Decisión de Daniel (2026-11-13): no se bloquea; antes de aplicar se
avisa en rojo «SKU · talla: baja de $X a $Y» y se pide confirmar, con
Cancelar por defecto. Si nada baja, el flujo queda igual que antes.

Puro: recibe los pares (variante_id, precio nuevo) del diálogo y las filas de
Inventario (las mismas que el diálogo muestra) con su `precio_venta`.
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
