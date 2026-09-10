"""Analítica sobre lo que de verdad se vende: la Libreta.

Hasta el 2026-09-10 la analítica del POS leía `venta` / `venta_detalle` /
`apartado` / `cliente`, tablas que quedaron en 8, 8, 7 y 6 registros (últimos
de marzo y abril). Las ventas reales viven en `libreta_venta`: cada operación
guarda su detalle con SKU, nombre, talla, precio, cantidad y subtotal, más la
empleada, la forma de pago y las comisiones.

Este servicio convierte esa bitácora en **filas analizables** (una por línea
de producto vendida) y las enriquece con el catálogo (escuela, pieza,
categoría, género, nivel). Sobre esas filas hay agregados puros: por
producto, escuela, empleada, día, hora y forma de pago.

Pensado como la base de datos de trabajo para la analítica pesada que Daniel
quiere alimentar (patrones de demanda, qué pedir, cuándo). Todo lo que no
toca la base es puro y testeable.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

_CENT = Decimal("0.01")
TIPOS_CON_PIEZAS = ("venta", "apartado")


def _d(valor) -> Decimal:
    try:
        return Decimal(str(valor if valor is not None else 0)).quantize(_CENT)
    except Exception:  # noqa: BLE001 — dato viejo o raro: no tumba el reporte
        return Decimal("0.00")


@dataclass(frozen=True)
class FilaVenta:
    """Una línea de producto vendida, lista para analizar."""

    momento: datetime
    tipo: str                 # venta | apartado
    sku: str
    nombre: str
    talla: str
    cantidad: int
    precio: Decimal
    importe: Decimal
    employee_code: str
    employee_name: str
    tarjeta: bool
    # Del catálogo (se llenan en `enriquecer`; vacíos si el SKU ya no existe)
    escuela: str = ""
    tipo_pieza: str = ""
    categoria: str = ""
    genero: str = ""
    nivel: str = ""

    @property
    def dia(self) -> date:
        return self.momento.date()

    @property
    def hora(self) -> int:
        return self.momento.hour


def _local(momento: datetime) -> datetime:
    return momento.astimezone().replace(tzinfo=None) if getattr(momento, "tzinfo", None) else momento


def desglosar(rows: list) -> list[FilaVenta]:
    """Cada operación de la Libreta → una fila por línea de producto (puro).

    Los abonos no traen prendas: no generan filas. Una línea sin `subtotal`
    se calcula con precio × cantidad.
    """
    filas: list[FilaVenta] = []
    for row in rows or []:
        tipo = str(getattr(row, "tipo", "") or "")
        if tipo not in TIPOS_CON_PIEZAS:
            continue
        momento = _local(row.created_at)
        for linea in (getattr(row, "detalle", None) or []):
            if not isinstance(linea, dict):
                continue
            cantidad = int(linea.get("cantidad") or 0)
            if cantidad <= 0:
                continue
            precio = _d(linea.get("precio"))
            importe = _d(linea.get("subtotal")) or (precio * cantidad).quantize(_CENT)
            filas.append(
                FilaVenta(
                    momento=momento,
                    tipo=tipo,
                    sku=str(linea.get("sku") or "").strip(),
                    nombre=str(linea.get("nombre") or "").strip(),
                    talla=str(linea.get("talla") or "").strip(),
                    cantidad=cantidad,
                    precio=precio,
                    importe=importe,
                    employee_code=str(getattr(row, "employee_code", "") or "").upper(),
                    employee_name=str(getattr(row, "employee_name", "") or ""),
                    tarjeta=bool(getattr(row, "pago_tarjeta", False)),
                )
            )
    return filas


def datos_de_catalogo(session, skus: list[str]) -> dict[str, dict]:
    """{sku: {escuela, tipo_pieza, categoria, genero, nivel}} en una consulta."""
    limpios = sorted({s for s in skus if s and s != "SIN-CODIGO"})
    if not limpios:
        return {}
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from pos_uniformes.database.models import Producto, Variante

    stmt = (
        select(Variante)
        .where(Variante.sku.in_(limpios))
        .options(
            selectinload(Variante.producto).selectinload(Producto.escuela),
            selectinload(Variante.producto).selectinload(Producto.tipo_pieza),
            selectinload(Variante.producto).selectinload(Producto.categoria),
            selectinload(Variante.producto).selectinload(Producto.nivel_educativo),
        )
    )
    salida: dict[str, dict] = {}
    for v in session.scalars(stmt).all():
        p = v.producto
        salida[str(v.sku)] = {
            "escuela": (p.escuela.nombre if p and p.escuela else ""),
            "tipo_pieza": (p.tipo_pieza.nombre if p and p.tipo_pieza else ""),
            "categoria": (p.categoria.nombre if p and p.categoria else ""),
            "genero": (p.genero or "") if p else "",
            "nivel": (p.nivel_educativo.nombre if p and p.nivel_educativo else ""),
        }
    return salida


def enriquecer(filas: list[FilaVenta], catalogo: dict[str, dict]) -> list[FilaVenta]:
    """Pega escuela / pieza / categoría / género / nivel a cada fila (puro)."""
    from dataclasses import replace

    if not catalogo:
        return list(filas)
    return [replace(f, **catalogo[f.sku]) if f.sku in catalogo else f for f in filas]


def filas_de_periodo(session, desde, hasta, *, incluir_privados: bool = True) -> list[FilaVenta]:
    """Todo junto: lee la Libreta del periodo y devuelve las filas enriquecidas."""
    from pos_uniformes.services.libreta_service import listar_operaciones, sin_privados

    rows = listar_operaciones(session, desde=desde, hasta=hasta, employee_code=None)
    if not incluir_privados:
        rows = sin_privados(rows)
    filas = desglosar(rows)
    return enriquecer(filas, datos_de_catalogo(session, [f.sku for f in filas]))


# ─── Agregados (puros) ───────────────────────────────────────────────────
@dataclass(frozen=True)
class Grupo:
    clave: str
    piezas: int
    importe: Decimal
    operaciones: int          # líneas distintas, no tickets

    @property
    def precio_promedio(self) -> Decimal:
        return (self.importe / self.piezas).quantize(_CENT) if self.piezas else Decimal("0.00")


def _agrupar(filas: list[FilaVenta], clave, *, minimo: str = "(sin dato)") -> list[Grupo]:
    acc: dict[str, list] = defaultdict(lambda: [0, Decimal("0.00"), 0])
    for f in filas:
        k = (clave(f) or "").strip() or minimo
        acc[k][0] += f.cantidad
        acc[k][1] += f.importe
        acc[k][2] += 1
    grupos = [Grupo(k, v[0], v[1].quantize(_CENT), v[2]) for k, v in acc.items()]
    return sorted(grupos, key=lambda g: (-g.importe, -g.piezas, g.clave))


def por_producto(filas: list[FilaVenta]) -> list[Grupo]:
    return _agrupar(filas, lambda f: f.nombre or f.sku)


def por_sku(filas: list[FilaVenta]) -> list[Grupo]:
    return _agrupar(filas, lambda f: f.sku)


def por_escuela(filas: list[FilaVenta]) -> list[Grupo]:
    return _agrupar(filas, lambda f: f.escuela, minimo="(sin escuela)")


def por_pieza(filas: list[FilaVenta]) -> list[Grupo]:
    return _agrupar(filas, lambda f: f.tipo_pieza, minimo="(sin pieza)")


def por_talla(filas: list[FilaVenta]) -> list[Grupo]:
    return _agrupar(filas, lambda f: f.talla, minimo="(sin talla)")


def por_empleada(filas: list[FilaVenta]) -> list[Grupo]:
    return _agrupar(filas, lambda f: f.employee_name or f.employee_code)


def por_dia(filas: list[FilaVenta]) -> list[Grupo]:
    grupos = _agrupar(filas, lambda f: f.dia.isoformat())
    return sorted(grupos, key=lambda g: g.clave)


def por_hora(filas: list[FilaVenta]) -> list[Grupo]:
    grupos = _agrupar(filas, lambda f: f"{f.hora:02d}:00")
    return sorted(grupos, key=lambda g: g.clave)


def por_forma_pago(filas: list[FilaVenta]) -> list[Grupo]:
    return _agrupar(filas, lambda f: "Tarjeta" if f.tarjeta else "Efectivo")


@dataclass(frozen=True)
class Resumen:
    piezas: int
    importe: Decimal
    lineas: int
    productos_distintos: int
    escuelas_distintas: int

    @property
    def ticket_promedio_por_pieza(self) -> Decimal:
        return (self.importe / self.piezas).quantize(_CENT) if self.piezas else Decimal("0.00")


def resumen(filas: list[FilaVenta]) -> Resumen:
    return Resumen(
        piezas=sum(f.cantidad for f in filas),
        importe=sum((f.importe for f in filas), Decimal("0.00")).quantize(_CENT),
        lineas=len(filas),
        productos_distintos=len({f.sku or f.nombre for f in filas}),
        escuelas_distintas=len({f.escuela for f in filas if f.escuela}),
    )
