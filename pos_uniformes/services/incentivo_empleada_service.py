"""Descuento de empleadas por su esfuerzo (Daniel, 2026-11-10).

«Les gustaría comprar con descuento, sentir que compran más barato, y que
puedan comprar más barato según su esfuerzo.»

- Lo que cada empleada vende en un mes le da su nivel de descuento para el
  mes SIGUIENTE. Se mide en comisiones (las mismas de la Libreta y de la meta
  semanal): las empleadas no ven montos.
- Lo que compran ellas mismas (ventas con descuento de empleada) no cuenta
  para la meta de nadie. Una venta borrada o anulada ya no está en la
  Libreta, así que tampoco cuenta.
- Tope al mes: hasta cierto importe (a precio de lista) compran con su
  nivel; de ahí en adelante, con el descuento base (5 %).
- La promo 3pz no lleva el nivel: se queda con el base.
- En el carrito se reparte renglón por renglón, en orden: el renglón que ya
  no cabe en lo que le queda del tope va con el base.

El % de cada renglón viaja en el propio renglón (`LLAVE_PCT`) y se guarda en
el detalle de la Libreta, para que la reimpresión y la corrección a tarjeta
usen el mismo que tuvo la venta.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, Mapping, Sequence

from pos_uniformes.services.fidelizacion.descuento_programa_service import LLAVE_PCT_EMPLEADA, es_promo_3pz

_CENT = Decimal("0.01")
_CERO = Decimal("0")

#: El 5 % de siempre: quien no llega a ningún nivel o ya pasó su tope.
PCT_BASE = Decimal("5")

#: Llave del renglón (carrito y detalle de la Libreta) con su % de empleada.
LLAVE_PCT = LLAVE_PCT_EMPLEADA

#: Tope por omisión: importe a precio de lista por mes con su nivel.
TOPE_POR_OMISION = Decimal("3000")

#: Tope del % que se puede configurar: arriba de esto se vende abajo del costo.
PCT_MAXIMO = Decimal("30")

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


@dataclass(frozen=True)
class Nivel:
    comisiones_minimas: int
    porcentaje: Decimal


#: Provisionales hasta calibrarlos con las ventas reales de la caja.
NIVELES_POR_OMISION: tuple[Nivel, ...] = (
    Nivel(0, Decimal("5")),
    Nivel(150, Decimal("10")),
    Nivel(250, Decimal("15")),
    Nivel(350, Decimal("20")),
)


class NivelesInvalidos(ValueError):
    """El texto se le muestra tal cual al dueño."""


# ─── Reglas puras ───────────────────────────────────────────────────────


def ordenar(niveles: Iterable[Nivel]) -> list[Nivel]:
    return sorted(niveles, key=lambda n: n.comisiones_minimas)


def validar(niveles: Sequence[Nivel], tope) -> tuple[list[Nivel], Decimal]:
    """Revisa lo que captura el dueño. Devuelve los niveles ordenados y el tope."""
    lista = ordenar(niveles)
    if not lista:
        raise NivelesInvalidos("Pon al menos un nivel.")
    if lista[0].comisiones_minimas != 0:
        raise NivelesInvalidos("El primer nivel debe empezar en 0 comisiones (es el de todas).")
    vistos: set[int] = set()
    anterior = None
    for n in lista:
        if n.comisiones_minimas < 0:
            raise NivelesInvalidos("Las comisiones no pueden ser negativas.")
        if n.comisiones_minimas in vistos:
            raise NivelesInvalidos(f"Hay dos niveles que empiezan en {n.comisiones_minimas} comisiones.")
        vistos.add(n.comisiones_minimas)
        pct = Decimal(str(n.porcentaje))
        if pct < 0 or pct > PCT_MAXIMO:
            raise NivelesInvalidos(f"El descuento debe ir de 0 a {PCT_MAXIMO.normalize():f} %.")
        if anterior is not None and pct <= anterior:
            raise NivelesInvalidos("Cada nivel debe dar más descuento que el anterior.")
        anterior = pct
    tope = Decimal(str(tope or 0)).quantize(_CENT)
    if tope < 0:
        raise NivelesInvalidos("El tope no puede ser negativo.")
    return lista, tope


def nivel_para(comisiones: int, niveles: Sequence[Nivel]) -> Nivel:
    """El nivel más alto alcanzado con esas comisiones."""
    lista = ordenar(niveles) or list(NIVELES_POR_OMISION)
    elegido = lista[0]
    for n in lista:
        if int(comisiones) >= n.comisiones_minimas:
            elegido = n
    return elegido


def siguiente_nivel(comisiones: int, niveles: Sequence[Nivel]) -> Nivel | None:
    for n in ordenar(niveles):
        if n.comisiones_minimas > int(comisiones):
            return n
    return None


def mes_anterior(ref: date) -> date:
    return date(ref.year - 1, 12, 1) if ref.month == 1 else date(ref.year, ref.month - 1, 1)


def mes_siguiente(ref: date) -> date:
    return date(ref.year + 1, 1, 1) if ref.month == 12 else date(ref.year, ref.month + 1, 1)


def ultimo_dia(ref: date) -> date:
    from datetime import timedelta

    return mes_siguiente(ref) - timedelta(days=1)


def importe_de(item: Mapping) -> Decimal:
    return (Decimal(str(item.get("precio", 0) or 0)) * int(item.get("cantidad", 0) or 0)).quantize(_CENT)


def repartir(items: Sequence[Mapping], *, pct_nivel, restante, pct_base=PCT_BASE) -> list[Decimal]:
    """El % de empleada de cada renglón, en orden.

    `restante` None = sin tope. Un renglón lleva el nivel si no es promo 3pz y
    su importe completo cabe en lo que queda del tope; si no, el base."""
    pct_nivel = Decimal(str(pct_nivel))
    pct_base = Decimal(str(pct_base))
    queda = None if restante is None else Decimal(str(restante))
    resultado: list[Decimal] = []
    for it in items:
        if pct_nivel <= pct_base or es_promo_3pz(it):
            resultado.append(pct_base)
            continue
        importe = importe_de(it)
        if queda is None or importe <= queda:
            resultado.append(pct_nivel)
            if queda is not None:
                queda -= importe
        else:
            resultado.append(pct_base)
    return resultado


def pct_de_renglon(item: Mapping, por_omision=PCT_BASE) -> Decimal:
    valor = item.get(LLAVE_PCT)
    return Decimal(str(valor)) if valor not in (None, "") else Decimal(str(por_omision))


def importe_con_nivel(detalle: Iterable[Mapping], pct_base=PCT_BASE) -> Decimal:
    """Lo que se compró con un % arriba del base (cuenta para el tope)."""
    base = Decimal(str(pct_base))
    return sum(
        (importe_de(line) for line in detalle if pct_de_renglon(line, base) > base),
        _CERO,
    ).quantize(_CENT)


def fmt_pct(pct) -> str:
    return f"{Decimal(str(pct)).normalize():f} %"


@dataclass(frozen=True)
class EstadoCompradora:
    """Con qué compra hoy una empleada."""

    codigo: str
    nombre: str
    porcentaje: Decimal
    tope: Decimal | None  # None = sin tope
    usado: Decimal

    @property
    def restante(self) -> Decimal | None:
        if self.tope is None:
            return None
        return max(self.tope - self.usado, _CERO).quantize(_CENT)

    @property
    def tiene_nivel(self) -> bool:
        return self.porcentaje > PCT_BASE

    def texto(self) -> str:
        if not self.tiene_nivel:
            return f"{self.nombre}: {fmt_pct(PCT_BASE)}"
        if self.restante is None:
            return f"{self.nombre}: {fmt_pct(self.porcentaje)}"
        return f"{self.nombre}: {fmt_pct(self.porcentaje)} (le quedan ${self.restante:,.2f} este mes)"


@dataclass(frozen=True)
class AvanceEmpleada:
    """Lo que ve ella en su Libreta."""

    pct_este_mes: Decimal
    restante_este_mes: Decimal | None
    comisiones_mes: int
    pct_mes_siguiente: Decimal
    siguiente: Nivel | None
    nombre_mes_siguiente: str

    def texto(self) -> str:
        partes = []
        if self.pct_este_mes > PCT_BASE:
            hoy = f"🏷 Este mes compras con {fmt_pct(self.pct_este_mes)}"
            if self.restante_este_mes is not None:
                hoy += f" (te quedan ${self.restante_este_mes:,.2f})"
            partes.append(hoy)
        else:
            partes.append(f"🏷 Este mes compras con {fmt_pct(PCT_BASE)}")
        mes = self.nombre_mes_siguiente
        if self.siguiente is None:
            partes.append(f"Vas en {self.comisiones_mes} comisiones: en {mes} compras con el máximo, {fmt_pct(self.pct_mes_siguiente)} 🎉")
        else:
            faltan = self.siguiente.comisiones_minimas - self.comisiones_mes
            partes.append(
                f"Vas en {self.comisiones_mes} comisiones: te faltan {faltan} "
                f"para comprar con {fmt_pct(self.siguiente.porcentaje)} en {mes}"
            )
        return " · ".join(partes)


# ─── Con la base ────────────────────────────────────────────────────────


def niveles(session) -> list[Nivel]:
    from sqlalchemy import select

    from pos_uniformes.database.models import NivelDescuentoEmpleada

    filas = session.scalars(select(NivelDescuentoEmpleada)).all()
    if not filas:
        return list(NIVELES_POR_OMISION)
    return ordenar(Nivel(int(f.comisiones_minimas), Decimal(str(f.porcentaje))) for f in filas)


def tope(session) -> Decimal | None:
    """None = sin tope (el dueño lo dejó en 0)."""
    from sqlalchemy import select

    from pos_uniformes.database.models import ConfiguracionNegocio

    conf = session.scalars(select(ConfiguracionNegocio).limit(1)).first()
    valor = getattr(conf, "tope_compra_empleada_mes", None) if conf else None
    valor = TOPE_POR_OMISION if valor is None else Decimal(str(valor))
    return None if valor <= 0 else valor


def _ventana(mes: date) -> tuple[datetime, datetime]:
    from pos_uniformes.services.libreta_service import ventana_rango

    return ventana_rango(date(mes.year, mes.month, 1), ultimo_dia(mes))


def comisiones_del_mes(session, employee_code: str, mes: date) -> int:
    """Lo que ella vendió ese mes, sin contar compras de empleadas."""
    from sqlalchemy import func, select

    from pos_uniformes.database.models import LibretaVenta

    desde, hasta = _ventana(mes)
    total = session.scalar(
        select(func.coalesce(func.sum(LibretaVenta.comisiones), 0)).where(
            func.upper(LibretaVenta.employee_code) == str(employee_code).upper(),
            LibretaVenta.descuento_empleada.is_(False),
            LibretaVenta.created_at >= desde,
            LibretaVenta.created_at <= hasta,
        )
    )
    return int(total or 0)


def usado_del_mes(session, compradora_code: str, mes: date) -> Decimal:
    from sqlalchemy import func, select

    from pos_uniformes.database.models import LibretaVenta

    desde, hasta = _ventana(mes)
    filas = session.scalars(
        select(LibretaVenta).where(
            func.upper(LibretaVenta.compradora_code) == str(compradora_code).upper(),
            LibretaVenta.descuento_empleada.is_(True),
            LibretaVenta.created_at >= desde,
            LibretaVenta.created_at <= hasta,
        )
    ).all()
    return sum((importe_con_nivel(f.detalle or []) for f in filas), _CERO).quantize(_CENT)


def estado_compradora(session, employee_code: str, nombre: str = "", *, hoy: date | None = None) -> EstadoCompradora:
    hoy = hoy or date.today()
    lista = niveles(session)
    nivel = nivel_para(comisiones_del_mes(session, employee_code, mes_anterior(hoy)), lista)
    return EstadoCompradora(
        codigo=str(employee_code).upper(),
        nombre=nombre or str(employee_code),
        porcentaje=Decimal(str(nivel.porcentaje)),
        tope=tope(session),
        usado=usado_del_mes(session, employee_code, hoy),
    )


def avance(session, employee_code: str, *, hoy: date | None = None) -> AvanceEmpleada:
    hoy = hoy or date.today()
    lista = niveles(session)
    este = estado_compradora(session, employee_code, hoy=hoy)
    com = comisiones_del_mes(session, employee_code, hoy)
    return AvanceEmpleada(
        pct_este_mes=este.porcentaje,
        restante_este_mes=este.restante,
        comisiones_mes=com,
        pct_mes_siguiente=Decimal(str(nivel_para(com, lista).porcentaje)),
        siguiente=siguiente_nivel(com, lista),
        nombre_mes_siguiente=MESES[mes_siguiente(hoy).month - 1],
    )


def empleadas_activas(session) -> list[tuple[str, str]]:
    from sqlalchemy import select

    from pos_uniformes.database.models import Empleada

    return [
        (e.codigo, e.nombre_completo)
        for e in session.scalars(
            select(Empleada).where(Empleada.activo.is_(True)).order_by(Empleada.nombre_completo)
        ).all()
    ]


def guardar(session, niveles_nuevos: Sequence[Nivel], tope_nuevo) -> None:
    """Reemplaza los niveles y el tope (los valida antes)."""
    from sqlalchemy import delete, select

    from pos_uniformes.database.models import ConfiguracionNegocio, NivelDescuentoEmpleada

    lista, tope_ok = validar(niveles_nuevos, tope_nuevo)
    session.execute(delete(NivelDescuentoEmpleada))
    for n in lista:
        session.add(NivelDescuentoEmpleada(comisiones_minimas=n.comisiones_minimas, porcentaje=Decimal(str(n.porcentaje))))
    conf = session.scalars(select(ConfiguracionNegocio).limit(1)).first()
    if conf is None:
        conf = ConfiguracionNegocio()
        session.add(conf)
    conf.tope_compra_empleada_mes = tope_ok
    session.flush()
