"""¿$4,200 es bueno? Comparar contra los mismos días de antes.

El bot daba cifras y ninguna manera de juzgarlas. Un número sin contexto no es
información: `$4,200` puede ser un viernes flojo o el mejor del mes, y Daniel
—que es quien tiene esa referencia en la cabeza— no siempre la tiene a la mano
estando lejos.

Dos decisiones que hacen que la comparación valga:

1. **Contra el MISMO día de la semana.** Una tienda de uniformes no vende igual
   un lunes que un sábado, ni al arrancar el ciclo escolar que a mitad de año.
   Comparar contra "ayer" dice más del calendario que del negocio.
2. **Hasta la MISMA hora.** A las 11 de la mañana llevas dos horas de venta;
   compararlas contra un día completo diría que vas hundido siempre. Esta es la
   diferencia entre una cifra en la que se puede confiar y una que enseña a
   ignorar al bot.

Los días en que no se vendió nada (cerrado, festivo) se saltan: promediar un
cero convierte un día bueno en uno malo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

_CENT = Decimal("0.01")

#: Cuántos "mismos días" se miran hacia atrás. Cuatro es un mes de ese día.
SEMANAS_ATRAS = 4

#: Debajo de esta diferencia se dice "como siempre": fingir precisión en el
#: ±3% es inventar una señal donde solo hay ruido.
UMBRAL_IGUAL_PCT = Decimal("8")

_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


@dataclass
class Comparativa:
    dia: date
    hasta_hora: int | None               # None = el día completo
    hoy: Decimal = Decimal("0.00")
    anteriores: list[tuple[date, Decimal]] = field(default_factory=list)

    @property
    def referencia(self) -> Decimal | None:
        """El promedio de los mismos días con venta. None si no hay con qué."""
        con_venta = [m for _, m in self.anteriores if m > 0]
        if not con_venta:
            return None
        return (sum(con_venta) / len(con_venta)).quantize(_CENT)

    @property
    def pct(self) -> Decimal | None:
        """Cuánto arriba o abajo, en porcentaje. None si no hay referencia."""
        ref = self.referencia
        if not ref:
            return None
        return (((self.hoy - ref) / ref) * 100).quantize(Decimal("1"))

    @property
    def mejor_de_los_mismos(self) -> bool:
        """¿Es el mejor de los días comparados?"""
        con_venta = [m for _, m in self.anteriores if m > 0]
        return bool(con_venta) and self.hoy > max(con_venta)


def ventas_hasta(session, dia: date, hora: int | None = None) -> Decimal:
    """Lo vendido ese día hasta esa hora (local). Sin hora, el día completo."""
    from pos_uniformes.services.corte_caja_service import resumir_periodo
    from pos_uniformes.services.libreta_service import listar_operaciones, ventana_hoy

    desde, hasta = ventana_hoy(dia)
    if hora is not None:
        corte = desde.replace(hour=0, minute=0, second=0) + timedelta(hours=hora)
        hasta = min(hasta, corte)
    if hasta <= desde:
        return Decimal("0.00")
    resumen = resumir_periodo(listar_operaciones(session, desde=desde, hasta=hasta))
    # Lo vendido, no lo que entró al cajón: los abonos de apartados viejos no
    # son venta de hoy y meterlos haría que la comparación mintiera.
    return Decimal(str(resumen.ventas)).quantize(_CENT)


def comparar(session, hoy: date | None = None, *, ahora: datetime | None = None) -> Comparativa:
    """Compara el día contra los mismos días de semanas anteriores."""
    ahora = ahora or datetime.now().astimezone()
    hoy = hoy or ahora.date()
    # Solo se corta por hora si el día que se mira es el de hoy y aún no cierra.
    hasta_hora: int | None = ahora.hour + 1 if hoy == ahora.date() else None
    if hasta_hora is not None and hasta_hora >= 24:
        hasta_hora = None

    comp = Comparativa(dia=hoy, hasta_hora=hasta_hora, hoy=ventas_hasta(session, hoy, hasta_hora))
    for semanas in range(1, SEMANAS_ATRAS + 1):
        antes = hoy - timedelta(weeks=semanas)
        comp.anteriores.append((antes, ventas_hasta(session, antes, hasta_hora)))
    return comp


def texto(comp: Comparativa) -> str:
    """Una línea para colgar de `/hoy`, el resumen o `/pulso`. Vacía si no hay con qué."""
    pct = comp.pct
    if pct is None:
        return ""
    dia = _DIAS[comp.dia.weekday()]
    momento = "a esta hora" if comp.hasta_hora is not None else "en todo el día"
    ref = comp.referencia

    # El orden importa: ganar por un pelo NO es "el mejor del mes". Anunciarlo
    # así por un 3% de diferencia —que es ruido— enseña a no creerle al bot, y
    # entonces tampoco se le cree el día que sí pasa algo.
    if abs(pct) < UMBRAL_IGUAL_PCT:
        return f"Como un {dia} normal {momento} (${ref:,.0f} de costumbre)"

    palabra = "arriba" if pct > 0 else "abajo"
    if comp.mejor_de_los_mismos:
        # Se dice las dos cosas: que destaca y cuánto. "El mejor" sin número no
        # deja juzgar si fue por mucho o por poco.
        return f"🔥 El mejor {dia} del mes {momento} · {abs(pct)}% {palabra} (${ref:,.0f})"
    flecha = "↑" if pct > 0 else "↓"
    return f"{flecha} {abs(pct)}% {palabra} de un {dia} normal {momento} (${ref:,.0f})"
