"""Lo de hoy en la pantalla de gafete: cuántas operaciones lleva cada una y
quién vendió al último.

Las empleadas lo pidieron (Daniel, 2026-11-07): ver su número de operaciones
ahí, desde que abrió la tienda y no desde el último corte. Sin montos: solo
cuántas y quién fue la última. Va chiquito, al pie de la tarjeta, para no
desentonar con la escena de temporada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time

from sqlalchemy import select

from pos_uniformes.database.models import LibretaVenta

#: Lo que cuenta como «operación» para la empleada: lo que se atiende en el
#: mostrador. Retiros, entradas y pagos no son operaciones suyas.
TIPOS_QUE_CUENTAN = ("venta", "apartado", "abono")


@dataclass(frozen=True)
class ResumenHoy:
    por_empleada: tuple[tuple[str, int], ...] = ()   # (nombre corto, operaciones), de más a menos
    ultima: tuple[str, str] | None = None             # (nombre corto, "16:42")
    desde: datetime | None = None

    @property
    def vacio(self) -> bool:
        return not self.por_empleada


def _corto(nombre: str, codigo: str) -> str:
    try:
        from pos_uniformes.services.nombres_empleadas_service import mostrar

        return mostrar(nombre or codigo, corto=True)
    except Exception:  # noqa: BLE001 — sin la tabla de nombres, el de pila
        return (nombre or codigo or "?").split()[0]


def _local(momento: datetime) -> datetime:
    return momento.astimezone().replace(tzinfo=None) if momento.tzinfo is not None else momento


def inicio_del_dia(hoy: date | None = None) -> datetime:
    """Desde la hora de apertura de la tienda, no desde el corte."""
    from pos_uniformes.services.horario_tienda_service import hora_apertura

    hoy = hoy or date.today()
    return datetime.combine(hoy, hora_apertura(hoy))


def resumen_de_hoy(session, *, hoy: date | None = None) -> ResumenHoy:
    desde = inicio_del_dia(hoy)
    filas = session.scalars(
        select(LibretaVenta)
        .where(
            LibretaVenta.created_at >= desde,
            LibretaVenta.created_at < datetime.combine(desde.date(), time.max),
            LibretaVenta.tipo.in_(TIPOS_QUE_CUENTAN),
            LibretaVenta.privado.is_(False),
        )
        .order_by(LibretaVenta.created_at)
    ).all()
    cuenta: dict[str, int] = {}
    nombres: dict[str, str] = {}
    for f in filas:
        cuenta[f.employee_code] = cuenta.get(f.employee_code, 0) + 1
        nombres[f.employee_code] = _corto(f.employee_name, f.employee_code)
    orden = sorted(cuenta.items(), key=lambda kv: (-kv[1], nombres[kv[0]].lower()))
    ultima = None
    if filas:
        f = filas[-1]
        ultima = (nombres[f.employee_code], _local(f.created_at).strftime("%H:%M"))
    return ResumenHoy(
        por_empleada=tuple((nombres[c], n) for c, n in orden), ultima=ultima, desde=desde,
    )


def texto(r: ResumenHoy) -> str:
    """«Hoy · Fanny 6 · Stayce 4 · Katherine 2    última: Fanny 16:42»; "" si no hay nada."""
    if r.vacio:
        return ""
    partes = "  ·  ".join(f"{nombre} {n}" for nombre, n in r.por_empleada)
    cola = f"      última: {r.ultima[0]} {r.ultima[1]}" if r.ultima else ""
    return f"Hoy  ·  {partes}{cola}"
