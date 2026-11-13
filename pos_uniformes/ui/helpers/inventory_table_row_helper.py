"""Filas visibles y tonos de la tabla de Inventario."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from pos_uniformes.services.inventario_donde_service import texto_donde, texto_donde_completo
from pos_uniformes.services.inventario_precio_service import aviso_precio, texto_precio
from pos_uniformes.services.inventario_existencia_service import (
    AGOTADO,
    BAJO_MINIMO,
    NEGATIVO,
    clasificar_existencia,
    es_fila_virtual,
    texto_existencia,
    tono_existencia,
)


INVENTORY_TABLE_HEADERS = (
    "SKU", "Prenda", "Talla", "Color", "Hay", "Dónde", "Precio", "Contada",
)
COLUMNA_STOCK = INVENTORY_TABLE_HEADERS.index("Hay")  # el total (tienda + bodega + piso)
COLUMNA_DONDE = INVENTORY_TABLE_HEADERS.index("Dónde")
COLUMNA_PRECIO = INVENTORY_TABLE_HEADERS.index("Precio")

#: Sin columna «Estado» (tanda 2): la talla desactivada se ve en gris y lo dice al pasar el mouse.
TEXTO_DESACTIVADA = "Desactivada: no se vende. Actívala desde su ficha."


@dataclass(frozen=True)
class InventoryTableRowView:
    variant_id: int
    values: tuple[object, ...]
    row_tone: str | None
    stock_tone: str
    tooltip: str | None = None
    #: (columna, texto) que gana sobre `tooltip` en esa celda.
    cell_tooltips: tuple[tuple[int, str], ...] = ()
    #: Si la cifra «Hay» lleva fondo de pastilla. La talla desactivada no: solo
    #: la letra en gris, como pide la norma (el tono va en el color del texto).
    #: Pendiente tanda 3: quitar también los demás fondos (cifra y filas en
    #: negativo o agotadas) y dejar el tono solo en el número.
    stock_con_fondo: bool = True


def build_inventory_table_row_views(visible_rows: list[dict[str, object]]) -> tuple[InventoryTableRowView, ...]:
    return tuple(build_inventory_table_row_view(row) for row in visible_rows)


def build_inventory_table_row_view(row: dict[str, object]) -> InventoryTableRowView:
    # La cifra es el TOTAL (tienda + bodega + piso), igual que chips y filtros.
    stock_total = int(row["stock_actual"])
    stock_bodega = int(row.get("stock_bodega", 0))
    stock_piso = int(row.get("stock_piso", 0))
    stock_minimo = row.get("stock_minimo")
    stock_minimo_int = int(stock_minimo) if stock_minimo is not None else None
    virtual = es_fila_virtual(row)
    clase = clasificar_existencia(stock_total, stock_minimo=stock_minimo_int, virtual=virtual)
    activa = bool(row["variante_activa"])
    # Desactivada: toda la fila en gris, también la cifra.
    stock_tone = tono_existencia(stock_total, stock_minimo=stock_minimo_int, virtual=virtual) if activa else "muted"
    row_tone = _build_inventory_row_tone(
        clase=clase,
        variant_active=activa,
    )
    conteo_raw = row.get("ultimo_conteo_at")
    conteo_text = _format_ultimo_conteo(conteo_raw if isinstance(conteo_raw, datetime) else None)
    return InventoryTableRowView(
        variant_id=int(row["variante_id"]),
        values=(
            row["sku"],
            row["producto_nombre_base"],
            row["talla"],
            row["color"],
            texto_existencia(stock_total, stock_minimo=stock_minimo_int, virtual=virtual),
            texto_donde(stock_total, stock_bodega, stock_piso, conjunto=virtual),
            texto_precio(row),
            conteo_text,
        ),
        row_tone=row_tone,
        stock_tone=stock_tone,
        tooltip=None if activa else TEXTO_DESACTIVADA,
        stock_con_fondo=activa,
        cell_tooltips=_cell_tooltips(
            (COLUMNA_DONDE, texto_donde_completo(stock_total, stock_bodega, stock_piso, conjunto=virtual)),
            (COLUMNA_PRECIO, aviso_precio(row)),
        ),
    )


def _format_ultimo_conteo(ultimo_conteo_at: datetime | None) -> str:
    if ultimo_conteo_at is None:
        return "Nunca"
    try:
        dt = ultimo_conteo_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = (datetime.now(tz=timezone.utc) - dt).days
        if days == 0:
            return "Hoy"
        if days == 1:
            return "Ayer"
        return f"Hace {days}d"
    except Exception:
        return "-"


def _build_inventory_row_tone(*, clase: str, variant_active: bool) -> str | None:
    if not variant_active:
        return "muted"
    if clase in (NEGATIVO, AGOTADO):
        return "danger"
    if clase == BAJO_MINIMO:
        return "warning"
    return None


def _cell_tooltips(*pares: tuple[int, str | None]) -> tuple[tuple[int, str], ...]:
    return tuple((columna, texto) for columna, texto in pares if texto)
