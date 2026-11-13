"""Reglas puras de la cara nueva de Inventario (tanda 3): orden, escaneo,
textos de la ficha y de la paginación, y los topes de impresión.

Sin Qt ni base: la vista (`ui/views/inventory_view.py`) solo las llama.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping, Sequence

from pos_uniformes.services.inventario_precio_service import precio_efectivo
from pos_uniformes.services.inventario_tarjetas_service import dias_desde_conteo
from pos_uniformes.services.talla_orden_service import clave_talla

# ── Orden al tocar el encabezado ─────────────────────────────────────────

#: Columna de la tabla → cómo se ordena. Lo que no está aquí no ordena.
ORDEN_POR_COLUMNA = ("SKU", "Prenda", "Talla", "Color", "Hay", "Dónde", "Precio", "Contada")


def _texto(valor: object) -> str:
    return _sin_acentos(str(valor or "")).casefold()


def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _entero(valor: object) -> int:
    try:
        return int(valor or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _decimal(valor: object) -> Decimal:
    try:
        return Decimal(str(valor)) if valor is not None else Decimal(0)
    except (InvalidOperation, ValueError):
        return Decimal(0)


def _clave(columna: str, fila: Mapping[str, object]) -> tuple:
    if columna == "SKU":
        return (_texto(fila.get("sku")),)
    if columna == "Prenda":
        return (_texto(fila.get("producto_nombre_base")), clave_talla(fila.get("talla")), _texto(fila.get("color")))
    if columna == "Talla":
        return (clave_talla(fila.get("talla")), _texto(fila.get("producto_nombre_base")))
    if columna == "Color":
        return (_texto(fila.get("color")), _texto(fila.get("producto_nombre_base")), clave_talla(fila.get("talla")))
    if columna == "Hay":
        return (_entero(fila.get("stock_actual")),)
    if columna == "Dónde":
        return (_entero(fila.get("stock_bodega")) + _entero(fila.get("stock_piso")),)
    if columna == "Precio":
        return (_decimal(precio_efectivo(fila)),)
    if columna == "Contada":
        # Nunca contada va primero (lo más viejo), luego de la más vieja a la más nueva.
        conteo = fila.get("ultimo_conteo_at")
        if not isinstance(conteo, datetime):
            return (0, 0.0)
        return (1, conteo.timestamp() if conteo.tzinfo else conteo.replace(tzinfo=None).timestamp())
    return ()


def ordenar_por_columna(filas: Sequence[Mapping[str, object]], columna: str | None, *, descendente: bool = False) -> list:
    """Ordena TODAS las filas filtradas (no solo la página) por esa columna.

    Sin columna o con una que no ordena, deja el orden de siempre (prenda y
    talla en orden de talla). El orden es estable: los empates conservan ese
    orden.
    """
    if not columna or columna not in ORDEN_POR_COLUMNA:
        return list(filas)
    return sorted(filas, key=lambda fila: _clave(columna, fila), reverse=descendente)


def siguiente_orden(actual: tuple[str | None, bool], columna: str) -> tuple[str | None, bool]:
    """Tocar un encabezado: 1.º ascendente, 2.º descendente, 3.º vuelve al orden de siempre."""
    columna_actual, descendente = actual
    if columna not in ORDEN_POR_COLUMNA:
        return actual
    if columna_actual != columna:
        return (columna, False)
    if not descendente:
        return (columna, True)
    return (None, False)


# ── Escaneo ──────────────────────────────────────────────────────────────


def buscar_sku_exacto(filas: Iterable[Mapping[str, object]], texto: str) -> object | None:
    """Si lo escrito o escaneado es el código exacto de una talla, su `variante_id`."""
    buscado = (texto or "").strip().casefold()
    if not buscado:
        return None
    for fila in filas:
        if str(fila.get("sku") or "").strip().casefold() == buscado:
            return fila.get("variante_id")
    return None


# ── Paginación ───────────────────────────────────────────────────────────


def texto_paginacion(total: int, pagina: int, tamano: int) -> str:
    """«Mostrando 1–100 de 214» (o «Sin tallas con estos filtros»)."""
    if total <= 0:
        return "Sin tallas con estos filtros"
    inicio = pagina * tamano + 1
    fin = min(total, (pagina + 1) * tamano)
    if inicio == 1 and fin == total:
        return f"Mostrando {total:,} {'talla' if total == 1 else 'tallas'}"
    return f"Mostrando {inicio:,}–{fin:,} de {total:,}"


# ── Textos de la ficha ───────────────────────────────────────────────────


def texto_contada(fila: Mapping[str, object], *, ahora: datetime) -> str:
    dias = dias_desde_conteo(fila, ahora=ahora)
    if dias is None:
        return "Nunca contada"
    if dias == 0:
        return "Contada hoy"
    if dias == 1:
        return "Contada ayer"
    return f"Contada hace {dias} días"


def texto_talla_color(fila: Mapping[str, object]) -> str:
    partes = []
    talla = str(fila.get("talla") or "").strip()
    color = str(fila.get("color") or "").strip()
    if talla:
        partes.append(f"Talla {talla}")
    if color:
        partes.append(color)
    return " · ".join(partes)


@dataclass(frozen=True)
class ResumenLote:
    tallas: int
    piezas: int

    @property
    def texto(self) -> str:
        return (
            f"{self.tallas:,} {'talla' if self.tallas == 1 else 'tallas'} · "
            f"{self.piezas:,} {'pieza' if self.piezas == 1 else 'piezas'}"
        )


def resumir_lote(filas: Iterable[Mapping[str, object]]) -> ResumenLote:
    """«12 tallas · 34 piezas»: las piezas suman solo lo positivo (un −2 no resta)."""
    tallas = piezas = 0
    for fila in filas:
        tallas += 1
        piezas += max(0, _entero(fila.get("stock_actual")))
    return ResumenLote(tallas=tallas, piezas=piezas)


# ── Topes de impresión y confirmación fuerte ─────────────────────────────

#: Más etiquetas que esto en un solo lote piden confirmar.
UMBRAL_CONFIRMAR_ETIQUETAS = 200

IMPRIMIR = "imprimir"
CONFIRMAR = "confirmar"
BLOQUEAR = "bloquear"
NADA = "nada"


def decidir_impresion_lote(cantidad: int, *, hay_filtro: bool, todo_lo_filtrado: bool = False) -> str:
    """imprimir | confirmar | bloquear | nada.

    «Imprimir todo lo filtrado» sin ningún filtro sería todo el catálogo (5,000+
    etiquetas): no se deja. Más de `UMBRAL_CONFIRMAR_ETIQUETAS` se pregunta.
    """
    if cantidad <= 0:
        return NADA
    if todo_lo_filtrado and not hay_filtro:
        return BLOQUEAR
    if cantidad > UMBRAL_CONFIRMAR_ETIQUETAS:
        return CONFIRMAR
    return IMPRIMIR


def confirmacion_coincide(escrito: str, esperado: str) -> bool:
    """Para eliminar hay que escribir el nombre: sin importar mayúsculas, acentos ni espacios de más."""

    def normal(texto: str) -> str:
        return " ".join(_sin_acentos(texto or "").casefold().split())

    return bool(normal(esperado)) and normal(escrito) == normal(esperado)


def contar_activos(valores: Iterable[object]) -> int:
    """Cuántos filtros de «Más filtros» están puestos (para «Más filtros (n)»)."""
    return sum(1 for valor in valores if valor)
