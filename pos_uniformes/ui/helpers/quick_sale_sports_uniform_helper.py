"""Promo 3pz (pants 2pz + playera) en Venta Rápida del satélite.

Reutiliza el flujo de caja (sale_sports_uniform_helper) sin tocarlo: las
filas del cache del satélite se envuelven en adaptadores que imitan la forma
variante.producto.tipo_prenda.nombre que esperan los detectores/diálogos.
Funciona igual online y offline porque el satélite siempre tiene
catalog_snapshot_rows cargado.
"""

from __future__ import annotations

from decimal import Decimal

from pos_uniformes.services.sports_uniform_pricing_service import THREE_PIECE_PLAYERA_PRICE
from pos_uniformes.ui.helpers.sale_sports_uniform_helper import (
    belongs_to_same_school,
    is_deportivo_playera_variant,
)

_PROMO_NAME_SUFFIX = " (promo 3pz)"


class _SchoolAdapter:
    def __init__(self, nombre: str) -> None:
        self.nombre = nombre


class _NamedAdapter:
    def __init__(self, nombre: str) -> None:
        self.nombre = nombre


class _ProductAdapter:
    def __init__(self, row: dict[str, object]) -> None:
        self.nombre = str(row.get("producto_nombre") or row.get("producto_nombre_base") or "")
        self.nombre_base = str(row.get("producto_nombre_base") or "")
        self.descripcion = str(row.get("producto_descripcion") or "")
        self.escuela_id = row.get("escuela_id")  # puede no existir → fallback por nombre
        self.escuela = _SchoolAdapter(str(row.get("escuela_nombre") or ""))
        self.tipo_prenda = _NamedAdapter(str(row.get("tipo_prenda_nombre") or ""))
        self.tipo_pieza = _NamedAdapter(str(row.get("tipo_pieza_nombre") or ""))


class CacheRowVariantAdapter:
    """Duck-type de Variante sobre una fila del cache del satélite."""

    def __init__(self, row: dict[str, object]) -> None:
        self.row = row
        self.sku = str(row.get("sku") or "").strip().upper()
        self.talla = str(row.get("talla") or "")
        self.color = str(row.get("color") or "")
        self.precio_venta = Decimal(str(row.get("precio_venta") or "0")).quantize(Decimal("0.01"))
        self.producto = _ProductAdapter(row)


def adapt_cache_row(row: dict[str, object] | None) -> CacheRowVariantAdapter | None:
    if row is None:
        return None
    return CacheRowVariantAdapter(row)


def load_playera_candidates_from_rows(
    rows: list[dict[str, object]],
    base_adapter: CacheRowVariantAdapter,
) -> list[CacheRowVariantAdapter]:
    """Playeras deportivas activas de la misma escuela que el pants base."""
    candidates: list[CacheRowVariantAdapter] = []
    for row in rows:
        if not row.get("producto_activo", True) or not row.get("variante_activo", True):
            continue
        adapter = CacheRowVariantAdapter(row)
        if not adapter.sku or adapter.sku == base_adapter.sku:
            continue
        if is_deportivo_playera_variant(adapter) and belongs_to_same_school(base_adapter, adapter):
            candidates.append(adapter)
    return candidates


def build_promo_playera_item(
    playera: CacheRowVariantAdapter,
    *,
    base_sku: str,
) -> dict[str, object]:
    """Línea de carrito de Venta Rápida para la playera en promo 3pz."""
    base_name = playera.producto.nombre_base or playera.producto.nombre or playera.sku
    return {
        "sku": playera.sku,
        "nombre": f"{base_name}{_PROMO_NAME_SUFFIX}",
        "talla": playera.talla,
        "color": playera.color,
        "precio": THREE_PIECE_PLAYERA_PRICE,
        "cantidad": 1,
        "precio_base": playera.precio_venta,
        "sports_uniform_role": "playera",
        "sports_uniform_base_sku": str(base_sku or "").strip().upper(),
    }


def mark_promo_base_item(item: dict[str, object], *, playera_sku: str) -> None:
    item["sports_uniform_role"] = "base"
    item["sports_uniform_playera_sku"] = str(playera_sku or "").strip().upper()


def restore_promo_playera_after_base_removed(
    items: list[dict[str, object]],
    removed_item: dict[str, object],
) -> str:
    """Si se quitó el pants base, la playera regresa a su precio original.

    Espejo de restore_sports_uniform_playera_price_if_needed de caja, con las
    llaves del carrito de Venta Rápida (precio/nombre).
    """
    if str(removed_item.get("sports_uniform_role") or "") != "base":
        return ""
    playera_sku = str(removed_item.get("sports_uniform_playera_sku") or "").strip().upper()
    if not playera_sku:
        return ""

    restored = False
    for item in items:
        if str(item.get("sku") or "").strip().upper() != playera_sku:
            continue
        if str(item.get("sports_uniform_role") or "") != "playera":
            continue
        if "precio_base" not in item:
            continue
        item["precio"] = item["precio_base"]
        name = str(item.get("nombre") or "")
        if name.endswith(_PROMO_NAME_SUFFIX):
            item["nombre"] = name[: -len(_PROMO_NAME_SUFFIX)]
        item.pop("precio_base", None)
        item.pop("sports_uniform_role", None)
        item.pop("sports_uniform_base_sku", None)
        restored = True

    if not restored:
        return ""
    return "Se quito el pants 2pz; la playera regreso a su precio original."
