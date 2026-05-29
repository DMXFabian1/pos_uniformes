"""Genera hojas de conteo pre-llenadas para impresora térmica de 80mm.

Cada hoja corresponde a un producto (agrupación de variantes por nombre)
y lista solo las tallas que existen, con espacios para que la empleada
escriba las existencias y el pedido a mano.
"""

from __future__ import annotations

import re
import textwrap
from datetime import datetime

from pos_uniformes.services.conteo_service import (
    VarianteParaConteo,
    obtener_variantes_agrupadas_por_producto,
)

# ── Box-drawing (38 cols, 80mm thermal) ─────────────────────────────────────

_W = 38
_IW = _W - 4  # ancho interno sin "│ " y " │"


def _top() -> str:
    return "┌" + "─" * (_W - 2) + "┐"


def _mid() -> str:
    return "├" + "─" * (_W - 2) + "┤"


def _bot() -> str:
    return "└" + "─" * (_W - 2) + "┘"


def _line(text: str) -> str:
    return f"│ {text:<{_IW}} │"


def _center(text: str) -> str:
    return f"│ {text:^{_IW}} │"


def _row(label: str, value: str) -> str:
    gap = _IW - len(label) - len(value)
    inner = f"{label}{' ' * max(1, gap)}{value}"
    return f"│ {inner:<{_IW}} │"


def _row3(c1: str, c2: str, c3: str, widths: tuple[int, int, int]) -> str:
    """Fila de 3 columnas con anchos fijos."""
    w1, w2, w3 = widths
    inner = f"{c1:<{w1}}{c2:^{w2}}{c3:^{w3}}"
    return f"│ {inner:<{_IW}} │"


# ── Builder ─────────────────────────────────────────────────────────────────

def build_conteo_sheets(
    session,
    escuela_id: int,
    escuela_nombre: str,
    fecha: str | None = None,
    nivel_id: int | None = None,
    nivel_nombre: str | None = None,
    escuela_num: str | None = None,
) -> list[str]:
    """Genera una lista de hojas de conteo (una por producto) como texto plano.

    Cada string es una hoja lista para imprimir en la térmica.
    """
    grupos = obtener_variantes_agrupadas_por_producto(session, escuela_id, nivel_id=nivel_id)
    if not grupos:
        return []

    fecha_str = fecha or datetime.now().strftime("%d/%m/%Y")

    # Filtrar virtuales primero para saber el total
    grupos_reales = [g for g in grupos if not g.get("virtual", False)]
    total_hojas = len(grupos_reales)
    sheets: list[str] = []

    for idx, grupo in enumerate(grupos_reales, start=1):
        producto_raw = grupo["producto_nombre"]
        tipo_pieza = grupo["tipo_pieza"]
        variantes: list[VarianteParaConteo] = grupo["variantes"]

        # Limpiar nombre: quitar escuela, "Ad hoc", pipes, y redundancias
        producto = producto_raw.split("|")[0].strip()
        producto = re.sub(re.escape(escuela_nombre), "", producto, flags=re.IGNORECASE).strip()
        producto = re.sub(r"\bAd\s+hoc\b", "", producto, flags=re.IGNORECASE).strip()
        producto = re.sub(r"\s{2,}", " ", producto).strip()
        if not producto:
            producto = tipo_pieza or producto_raw

        if not variantes:
            continue

        # Extraer colores únicos (ignorar "Sin color" y vacíos)
        colores = sorted({
            v.color for v in variantes
            if v.color and v.color.lower() not in ("sin color", "")
        })
        color_str = ", ".join(colores) if colores else ""

        lines: list[str] = []
        lines.append(_top())
        titulo = f"HOJA DE CONTEO {idx}/{total_hojas}"
        if escuela_num:
            titulo += f"  ({escuela_num})"
        lines.append(_center(titulo))
        lines.append(_mid())

        # Encabezado
        lines.append(_line(f"Escuela: {escuela_nombre}"))
        if nivel_nombre:
            lines.append(_line(f"Nivel:   {nivel_nombre}"))
        lines.append(_line(f"Fecha:   {fecha_str}"))
        lines.append(_mid())

        # Nombre del producto (wrap si es largo)
        for part in textwrap.wrap(producto, width=_IW):
            lines.append(_center(part))

        if tipo_pieza and tipo_pieza not in producto:
            lines.append(_center(tipo_pieza))

        if color_str:
            for part in textwrap.wrap(color_str, width=_IW):
                lines.append(_center(part))

        lines.append(_mid())

        # Encabezados de columnas
        # Talla | Exist. | Pedido
        col_widths = (14, 10, 10)
        lines.append(_row3("Talla", "Exist.", "Pedido", col_widths))
        lines.append(_mid())

        # Filas de tallas
        for v in variantes:
            talla = v.talla or "U"
            # Exist. y Pedido vacíos — la empleada los llena a mano
            lines.append(_row3(talla, "____", "____", col_widths))

        lines.append(_bot())

        # Espacio para firma
        lines.append("")
        lines.append(f"  Contó: {'_' * 24}")
        lines.append("")
        lines.append("")

        sheets.append("\n".join(lines))

    return sheets


def build_conteo_sheets_combined(
    session,
    escuela_id: int,
    escuela_nombre: str,
    fecha: str | None = None,
    nivel_id: int | None = None,
) -> str:
    """Genera todas las hojas de conteo concatenadas en un solo string.

    Separadas por líneas vacías para que la térmica las imprima en secuencia.
    """
    sheets = build_conteo_sheets(session, escuela_id, escuela_nombre, fecha, nivel_id=nivel_id)
    return "\n\n".join(sheets)
