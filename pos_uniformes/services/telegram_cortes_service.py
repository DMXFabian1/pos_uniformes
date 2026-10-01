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
    #: El dueño bajó (o subió) la cifra a mano con «Ajustar la venta».
    ajustado: bool = False
    #: Por qué se ajustó. Vacío en los de antes de que se pidiera.
    nota: str = ""

    @property
    def diferencia(self) -> Decimal:
        return (self.contado - self.esperado).quantize(_CENT)

    @property
    def llama_la_atencion(self) -> bool:
        """Un ajuste del dueño no es un descuadre: él mismo lo puso.

        Lo que merece mirarse es cuando la caja no cuadra sin que nadie lo
        haya decidido (Daniel, 2026-10-01: esos 'faltó $2,000' eran sus
        ajustes, no dinero perdido)."""
        return not self.ajustado and abs(self.diferencia) >= OJO


def _quien(code: str) -> str:
    from pos_uniformes.services.nombres_empleadas_service import mostrar

    return mostrar(code)


def ultimos(session: Session, *, dias: int = 14, tope: int = TOPE) -> list[CorteFila]:
    """Los cortes más recientes, del más nuevo al más viejo."""
    from pos_uniformes.database.models import LibretaCorte
    from pos_uniformes.services.historial_cortes_service import venta_oficial, venta_real

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
                ajustado=bool(venta_real(c) is not None and venta_real(c) != venta_oficial(c)),
                nota=str(c.nota or ""),
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
        elif c.ajustado:
            signo = "+" if c.diferencia > 0 else "−"
            marca = f"✏️ ajustado {signo}${abs(c.diferencia):,.2f}"
            if c.nota:
                marca += f" · {c.nota}"
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
        # Lo que se ajusta a mano no entra aquí: eso lo decidió el dueño.
    else:
        lineas.append(f"{cuadrados} cuadraron exacto y ninguno se pasa de ${OJO:,.0f}. 👍")
    ajustados = [c for c in filas if c.ajustado]
    if ajustados:
        suma = sum((c.diferencia for c in ajustados), Decimal("0"))
        lineas.append(f"{len(ajustados)} con ajuste tuyo, {'−' if suma < 0 else '+'}${abs(suma):,.2f} en total.")
        sin_decir = [c for c in ajustados if not c.nota]
        if sin_decir:
            lineas.append(f"{len(sin_decir)} de ellos sin decir por qué (son de antes).")
    return "\n".join(lineas)


def resumen(session: Session, *, dias: int = 14) -> str:
    return texto(ultimos(session, dias=dias), dias=dias)
