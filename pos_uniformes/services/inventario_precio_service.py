"""Columna «Precio» de Inventario (tanda 2, 2026-11-13).

- El precio en formato de la tienda: «$320», «$1,250», «$99.50».
- Si la talla tiene Oferta o Liquidación vigente, el precio rebajado con una
  marca corta: «Oferta $175». El precio normal va en el aviso al pasar el
  mouse («Precio normal $250 · hasta el 30/11/2026»).

Las rebajas se leen UNA vez por carga del listado (`rebaja_service.vigentes_por_sku`)
y se pegan a las filas aquí, sin una consulta por talla.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable, Mapping, MutableMapping

from pos_uniformes.services.rebaja_service import ETIQUETAS, RebajaVigente, fmt_corto

LLAVE_TIPO = "rebaja_tipo"
LLAVE_PRECIO = "rebaja_precio"
LLAVE_HASTA = "rebaja_hasta"


def adjuntar_rebajas(
    filas: Iterable[MutableMapping[str, object]],
    vigentes: Mapping[str, RebajaVigente],
) -> None:
    """Pega a cada fila su rebaja vigente (o None) buscando por SKU."""
    for fila in filas:
        rebaja = vigentes.get(str(fila.get("sku") or "").upper()) if vigentes else None
        fila[LLAVE_TIPO] = rebaja.tipo if rebaja else None
        fila[LLAVE_PRECIO] = rebaja.precio if rebaja else None
        fila[LLAVE_HASTA] = rebaja.hasta if rebaja else None


def texto_precio(fila: Mapping[str, object]) -> str:
    """«$320» o, con rebaja vigente, «Oferta $175» / «Liquidación $150»."""
    precio = fila.get("precio_venta")
    tipo = fila.get(LLAVE_TIPO)
    rebajado = fila.get(LLAVE_PRECIO)
    if tipo and rebajado is not None:
        return f"{ETIQUETAS.get(str(tipo), str(tipo))} {fmt_corto(rebajado)}"
    if precio in (None, ""):
        return "—"
    return fmt_corto(precio)


def aviso_precio(fila: Mapping[str, object]) -> str | None:
    """El precio normal cuando hay rebaja; None si no hay nada que aclarar."""
    tipo = fila.get(LLAVE_TIPO)
    if not tipo or fila.get(LLAVE_PRECIO) is None or fila.get("precio_venta") in (None, ""):
        return None
    texto = f"Precio normal {fmt_corto(fila['precio_venta'])}"
    hasta = fila.get(LLAVE_HASTA)
    if isinstance(hasta, date):
        texto += f" · {ETIQUETAS.get(str(tipo), str(tipo))} hasta el {hasta:%d/%m/%Y}"
    return texto
