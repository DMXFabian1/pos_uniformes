"""Los últimos cortes, con lo que faltó o sobró.

Un corte con $300 de diferencia no enteraba a nadie hasta que alguien lo
buscaba en la PC (Daniel, 2026-09-25: "lo principal son los cortes y el
dinero"). Esto lo pone en el celular.

La diferencia es siempre **contado − esperado**: positiva sobró, negativa
faltó. Misma cuenta que el resumen de la noche.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

_CENT = Decimal("0.01")

#: Cuántos cortes caben en un mensaje de celular sin volverse un muro.
TOPE = 10

#: A partir de aquí una diferencia deja de ser "redondeo" y merece mirarse.
OJO = Decimal("50.00")


@dataclass(frozen=True)
class CorteFila:
    fecha: date
    hora: str
    quien: str
    contado: Decimal
    esperado: Decimal
    operaciones: int

    @property
    def diferencia(self) -> Decimal:
        return (self.contado - self.esperado).quantize(_CENT)

    @property
    def llama_la_atencion(self) -> bool:
        return abs(self.diferencia) >= OJO


def _quien(code: str) -> str:
    from pos_uniformes.services.nombres_empleadas_service import mostrar

    return mostrar(code)


def ultimos(session: Session, *, dias: int = 14, tope: int = TOPE) -> list[CorteFila]:
    """Los cortes más recientes, del más nuevo al más viejo."""
    from pos_uniformes.database.models import LibretaCorte

    desde = date.today() - timedelta(days=int(dias))
    filas = session.scalars(
        select(LibretaCorte)
        .where(LibretaCorte.fecha >= desde)
        .order_by(LibretaCorte.fecha.desc(), LibretaCorte.id.desc())
        .limit(int(tope))
    ).all()

    salida = []
    for c in filas:
        momento = c.hasta or c.created_at
        momento = momento.astimezone() if momento and momento.tzinfo else momento
        salida.append(
            CorteFila(
                fecha=c.fecha,
                hora=momento.strftime("%H:%M") if momento else "",
                quien=_quien(str(c.creado_por or "")),
                contado=Decimal(str(c.monto_final or 0)),
                esperado=Decimal(str(c.monto_esperado or 0)),
                operaciones=int(c.operaciones or 0),
            )
        )
    return salida


def texto(filas: list[CorteFila], *, dias: int = 14) -> str:
    """Los cortes como se leen en el celular."""
    if not filas:
        return f"No hay cortes en los últimos {dias} días."

    _DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
    lineas = [f"🧾 Últimos cortes ({len(filas)}):", ""]
    cuadrados = 0
    for c in filas:
        dia = f"{_DIAS[c.fecha.weekday()]} {c.fecha:%d/%m}"
        if c.diferencia == 0:
            cuadrados += 1
            marca = "✅ cuadró"
        else:
            señal = "⚠️" if c.llama_la_atencion else "·"
            verbo = "sobró" if c.diferencia > 0 else "faltó"
            marca = f"{señal} {verbo} ${abs(c.diferencia):,.2f}"
        lineas.append(f"{dia} {c.hora} · ${c.contado:,.2f} — {marca}")
        lineas.append(f"   {c.quien} · {c.operaciones} ops")

    ojo = [c for c in filas if c.llama_la_atencion]
    lineas.append("")
    if ojo:
        peor = max(ojo, key=lambda c: abs(c.diferencia))
        lineas.append(
            f"{len(ojo)} de {len(filas)} se pasan de ${OJO:,.0f}. "
            f"El más: {peor.fecha:%d/%m} con ${abs(peor.diferencia):,.2f}."
        )
        # Cuando falta casi siempre y en cifras redondas, lo más probable no es
        # un descuadre: es dinero que salió sin quedar apuntado.
        faltaron = [c for c in ojo if c.diferencia < 0]
        redondas = [c for c in faltaron if abs(c.diferencia) % 100 == 0]
        if len(redondas) >= 3 and len(redondas) * 2 >= len(faltaron):
            lineas.append("")
            lineas.append(
                "Casi todas son cifras redondas: suena a dinero que saliste "
                "y no quedó apuntado. Con /retiro 2000 banco queda anotado y "
                "el corte cuadra solo."
            )
    else:
        lineas.append(f"{cuadrados} cuadraron exacto y ninguno se pasa de ${OJO:,.0f}. 👍")
    return "\n".join(lineas)


def resumen(session: Session, *, dias: int = 14) -> str:
    return texto(ultimos(session, dias=dias), dias=dias)
