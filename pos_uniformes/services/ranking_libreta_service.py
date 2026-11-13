"""Ranking de empleadas sobre la Libreta (`LibretaVenta`), la fuente de
ventas vigente (kioskos). Reemplaza al ranking del POS formal, que leía
`Venta`/`Apartado`, tablas que ya no reciben ventas (auditoría 2026-11-08).

Cada métrica va por separado para no mezclar cosas distintas:

- puntos: las comisiones (lo que se paga). Es el orden del ranking;
- piezas y operaciones: solo ventas y apartados (un abono no es una venta);
- importe de ventas: solo tipo venta (valor de venta, no dinero cobrado);
- apartados: cuántos y por cuánto (su valor completo, una sola vez);
- abonos: cuántos y cuánto, aparte y a nombre de quien los COBRÓ. No se
  suman al importe del apartado: eso contaría el mismo dinero dos veces.

Sin restricciones de privacidad (decisión de Daniel, 2026-11-08): el
ranking vive en Configuración, que solo abre el administrador.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from pos_uniformes.services.libreta_service import (
    TIPOS_OPERACION,
    cuenta_como_operacion,
    es_compra_de_empleada,
)

_CENT = Decimal("0.01")


#: Para el ranking, operaciones y piezas son solo ventas y apartados (ver
#: arriba: un abono no es una venta). Desde 2026-11-12 es la regla única
#: (`libreta_service.TIPOS_OPERACION`, Daniel: los abonos «no cuentan como
#: operación»); el nombre se queda por compatibilidad.
TIPOS_OPERACION_RANKING = TIPOS_OPERACION


@dataclass
class FilaRanking:
    employee_code: str
    nombre: str
    puntos: int = 0
    piezas: int = 0
    operaciones: int = 0
    ventas: int = 0
    importe_ventas: Decimal = field(default_factory=lambda: Decimal("0.00"))
    apartados: int = 0
    importe_apartados: Decimal = field(default_factory=lambda: Decimal("0.00"))
    abonos: int = 0
    importe_abonos: Decimal = field(default_factory=lambda: Decimal("0.00"))
    posicion: int = 0


def _monto(row) -> Decimal:
    return Decimal(str(getattr(row, "monto_total", 0) or 0)).quantize(_CENT)


def calcular(rows) -> list[FilaRanking]:
    """Agrupa por código de gafete (no por nombre) y ordena por puntos,
    luego piezas, luego código. Quien solo cobró abonos aparece con 0
    puntos (sale en la sección de abonos)."""
    filas: dict[str, FilaRanking] = {}
    for row in rows or []:
        code = str(getattr(row, "employee_code", "") or "").strip().upper()
        if not code:
            continue
        fila = filas.get(code)
        if fila is None:
            fila = filas[code] = FilaRanking(employee_code=code, nombre=code)
        nombre = str(getattr(row, "employee_name", "") or "").strip()
        if nombre:
            fila.nombre = nombre
        tipo = str(getattr(row, "tipo", "") or "")
        # Los puntos se suman tal cual están guardados (los abonos valen 0).
        fila.puntos += int(getattr(row, "comisiones", 0) or 0)
        if es_compra_de_empleada(row):
            # La regla única (libreta_service, 2026-11-12): su propia compra
            # con precio especial no le suma operación, piezas ni importe.
            continue
        if cuenta_como_operacion(row, TIPOS_OPERACION_RANKING):
            fila.operaciones += 1
            fila.piezas += int(getattr(row, "piezas", 0) or 0)
        if tipo == "venta":
            fila.ventas += 1
            fila.importe_ventas += _monto(row)
        elif tipo == "apartado":
            fila.apartados += 1
            fila.importe_apartados += _monto(row)
        elif tipo == "abono":
            fila.abonos += 1
            fila.importe_abonos += _monto(row)
    ordenadas = sorted(filas.values(), key=lambda f: (-f.puntos, -f.piezas, f.employee_code))
    for i, fila in enumerate(ordenadas, start=1):
        fila.posicion = i
    return ordenadas


def cargar(session, desde: date, hasta: date) -> list[FilaRanking]:
    """Ranking del rango de días (inclusive, hora local de la tienda)."""
    from pos_uniformes.services.libreta_service import listar_operaciones, ventana_rango

    inicio, fin = ventana_rango(desde, hasta)
    return calcular(listar_operaciones(session, desde=inicio, hasta=fin))
