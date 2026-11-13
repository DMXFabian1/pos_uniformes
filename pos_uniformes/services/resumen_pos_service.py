"""La pestaña Resumen del POS, desde la Libreta (2026-11-12).

Daniel (2026-11-12): «la caja antigua ya no es de utilidad, todo lo demás
corre en libreta y kioskos» → «Pantallas con datos viejos». La tarjeta
«Ventas» y el «Ingreso confirmado» del Resumen contaban la tabla `venta` de
la Caja antigua, que ya no crece: enseñaban siempre los números de abril.

Aquí salen de la Libreta (`libreta_venta`), con las mismas reglas que el
resto del sistema:

- **Operaciones**: la regla única `libreta_service.cuenta_como_operacion`
  (venta y apartado; ni el abono ni la compra de una empleada con precio
  especial).
- **Ventas**: las operaciones de tipo venta, con esa misma regla.
- **Cobrado**: solo dinero real, sin sumar apartados (como
  `resumen_diario_service.texto_hoy`): efectivo + lo que llega por la
  terminal, de ventas, abonos y la diferencia cobrada en un cambio de
  prenda, con los ajustes del dueño en sus cortes (la cifra oficial). Se
  suma con `corte_caja_service.resumir_periodo`, la misma regla del corte y
  del bot, y sin las compras a cuenta de las empleadas
  (`corte_caja_service.sin_compras_a_cuenta`): ese dinero no entró al cajón
  (revisión, 2026-11-12).
- **Anuladas**: una operación anulada o borrada se elimina de la Libreta
  (`libreta_service.anular_operacion_con_monedero` / `eliminar_operacion`),
  así que ya no está en las filas y no cuenta.
- **Privadas**: el dinero de una operación privada solo lo ve el dueño;
  `incluir_privados=False` la quita (ver `libreta_service.sin_privados`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

_CENT = Decimal("0.01")


@dataclass(frozen=True)
class CifrasPeriodo:
    operaciones: int = 0
    ventas: int = 0
    apartados: int = 0
    piezas: int = 0
    cobrado: Decimal = field(default_factory=lambda: Decimal("0.00"))


@dataclass(frozen=True)
class ResumenPos:
    hoy: CifrasPeriodo
    mes: CifrasPeriodo


def cifras_periodo(rows: list, *, ajuste: Decimal = Decimal("0.00"), incluir_privados: bool = True) -> CifrasPeriodo:
    """Las cifras de un periodo a partir de sus filas de la Libreta (puro)."""
    from pos_uniformes.services.corte_caja_service import resumir_periodo
    from pos_uniformes.services.libreta_service import contar_operaciones, cuenta_como_operacion, sin_privados

    rows = list(rows or [])
    if not incluir_privados:
        rows = sin_privados(rows)
    operaciones = [r for r in rows if cuenta_como_operacion(r)]
    # Como el corte y el bot: todas las filas (el cambio de prenda también
    # mete dinero), el apartado no es dinero (resumir_periodo lo separa).
    r = resumir_periodo(rows)
    return CifrasPeriodo(
        # Ventas unidas en una operación cuentan 1 (2026-11-13).
        operaciones=contar_operaciones(operaciones),
        ventas=contar_operaciones(operaciones, ("venta",)),
        apartados=contar_operaciones(operaciones, ("apartado",)),
        piezas=sum(int(getattr(r, "piezas", 0) or 0) for r in operaciones),
        cobrado=(r.efectivo + Decimal(ajuste or 0) + r.tarjeta_neto).quantize(_CENT),
    )


def cargar(session, hoy: date | None = None, *, incluir_privados: bool = True) -> ResumenPos:
    """Hoy y el mes en curso (del día 1 a hoy), leídos de la Libreta."""
    from pos_uniformes.services.analitica_tablero_service import limites
    from pos_uniformes.services.corte_caja_service import ajustes_en_rango, sin_compras_a_cuenta
    from pos_uniformes.services.libreta_service import listar_operaciones

    hoy = hoy or date.today()
    ini_mes, fin = limites(hoy.replace(day=1), hoy)
    ini_hoy, _ = limites(hoy, hoy)
    # La compra a cuenta de una empleada no es dinero que entró al cajón: el
    # corte y el bot la quitan igual (revisión, 2026-11-12).
    rows_mes = sin_compras_a_cuenta(session, listar_operaciones(session, desde=ini_mes, hasta=fin, employee_code=None))
    rows_hoy = sin_compras_a_cuenta(session, listar_operaciones(session, desde=ini_hoy, hasta=fin, employee_code=None))
    return ResumenPos(
        hoy=cifras_periodo(
            rows_hoy, ajuste=ajustes_en_rango(session, ini_hoy, fin), incluir_privados=incluir_privados
        ),
        mes=cifras_periodo(
            rows_mes, ajuste=ajustes_en_rango(session, ini_mes, fin), incluir_privados=incluir_privados
        ),
    )
