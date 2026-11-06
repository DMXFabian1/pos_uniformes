"""¿El contador de personas está contando, y lo que cuenta se parece a la realidad?

Daniel, 2026-11-06: «¿hay margen de mejora para el sistema de cámaras?» → lo
primero era comprobar lo que nunca se comprobó. Si el contador se cae, hoy lo
único que se ve es una tabla vacía días después. Esto lee `afluencia_hora` y
las ventas de la Libreta y dice, con sus razones, qué está mal:

- nunca ha contado / dejó de contar;
- días con ventas y sin nadie entrando;
- más ventas que personas que entraron (cuenta de menos);
- entran y salen cantidades muy distintas (la línea o el lado están mal:
  quien entra, sale);
- una cámara de puerta que no cuenta nada mientras la otra sí.

Lo que NO puede decir es si el número es exacto: eso solo sale contando a
mano un rato y comparando. El texto lo dice, para que un «todo bien» no se
lea como más de lo que es.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select

from pos_uniformes.database.models import AfluenciaHora
from pos_uniformes.services.afluencia_service import _hora_local, listar_afluencia, ventas_por_hora

#: Con menos ventas que esto en un día, «nadie entró» no prueba nada.
VENTAS_PARA_JUZGAR = 3
#: Entradas y salidas del mismo día deberían parecerse. Más lejos que esto, algo anda mal.
DESBALANCE_TOLERADO = 0.4
#: Y con menos cruces que esto, la diferencia es puro ruido.
CRUCES_PARA_JUZGAR = 20
_DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")


@dataclass(frozen=True)
class DiaRevisado:
    dia: date
    entradas: int = 0
    salidas: int = 0
    pasan: int = 0
    ventas: int = 0

    @property
    def conversion(self) -> float | None:
        return round(100.0 * self.ventas / self.entradas, 1) if self.entradas > 0 else None


@dataclass(frozen=True)
class Revision:
    hoy: date
    ultimo_dato: datetime | None                 # hora local, sin zona
    dias: tuple[DiaRevisado, ...] = ()
    por_camara: dict[str, tuple[int, int, int]] = field(default_factory=dict)   # entradas, salidas, pasan
    hallazgos: tuple[str, ...] = ()

    @property
    def sano(self) -> bool:
        return not self.hallazgos


def _dia_corto(d: date) -> str:
    return f"{_DIAS[d.weekday()]} {d.day}/{d.month}"


def _local(momento: datetime | None) -> datetime | None:
    if momento is None:
        return None
    return momento.astimezone().replace(tzinfo=None) if momento.tzinfo is not None else momento


def revisar(session, *, hoy: date | None = None, dias: int = 7, ahora: datetime | None = None) -> Revision:
    """Los últimos `dias` días (sin contar hoy, que va a medias) y lo que se ve mal."""
    ahora = ahora or datetime.now()
    hoy = hoy or ahora.date()
    desde = datetime.combine(hoy - timedelta(days=dias), time.min)
    hasta = datetime.combine(hoy, time.max)

    ultimo = _local(session.scalar(select(func.max(AfluenciaHora.updated_at))))
    filas = listar_afluencia(session, desde=desde, hasta=hasta)
    ventas = ventas_por_hora(session, desde=desde, hasta=hasta)

    por_dia: dict[date, dict[str, int]] = {}
    por_camara: dict[str, list[int]] = {}
    for f in filas:
        dia = _hora_local(f.hora).date()
        d = por_dia.setdefault(dia, {"entradas": 0, "salidas": 0, "pasan": 0})
        d["entradas"] += int(f.entradas or 0)
        d["salidas"] += int(f.salidas or 0)
        d["pasan"] += int(f.pasan or 0)
        c = por_camara.setdefault(f.camara, [0, 0, 0])
        c[0] += int(f.entradas or 0)
        c[1] += int(f.salidas or 0)
        c[2] += int(f.pasan or 0)
    ventas_dia: dict[date, int] = {}
    for hora, n in ventas.items():
        ventas_dia[hora.date()] = ventas_dia.get(hora.date(), 0) + n

    revisados = tuple(
        DiaRevisado(dia=d, ventas=ventas_dia.get(d, 0), **por_dia.get(d, {}))
        for d in (hoy - timedelta(days=i) for i in range(dias, 0, -1))
        if d in por_dia or ventas_dia.get(d, 0)
    )

    hallazgos: list[str] = []
    if ultimo is None:
        hallazgos.append(
            "El contador NUNCA ha escrito nada: no está instalado en la PC principal o no arranca. "
            "Corre afluencia\\diagnostico_afluencia.bat y manda el reporte."
        )
    else:
        # ¿Dejó de contar? Se juzga contra el último día que hubo ventas.
        dias_con_venta = [d.dia for d in revisados if d.ventas >= VENTAS_PARA_JUZGAR]
        if dias_con_venta and ultimo.date() < max(dias_con_venta):
            hallazgos.append(
                f"El contador se detuvo: su último dato es del {_dia_corto(ultimo.date())} a las "
                f"{ultimo:%H:%M} y después hubo ventas."
            )
        sin_gente = [d for d in revisados if d.ventas >= VENTAS_PARA_JUZGAR and d.entradas == 0]
        if sin_gente:
            hallazgos.append(
                "Días con ventas y sin nadie entrando: "
                + ", ".join(f"{_dia_corto(d.dia)} ({d.ventas} ventas)" for d in sin_gente)
                + ". Ese día no contó."
            )
        de_menos = [d for d in revisados if d.entradas > 0 and d.ventas > d.entradas]
        if de_menos:
            hallazgos.append(
                "Más ventas que personas que entraron: "
                + ", ".join(f"{_dia_corto(d.dia)} ({d.ventas} ventas, {d.entradas} entran)" for d in de_menos)
                + ". Está contando de menos: revisa las líneas de las puertas."
            )
        entran = sum(d.entradas for d in revisados)
        salen = sum(d.salidas for d in revisados)
        if entran + salen >= CRUCES_PARA_JUZGAR and abs(entran - salen) > DESBALANCE_TOLERADO * max(entran, salen):
            hallazgos.append(
                f"Entraron {entran} y salieron {salen}: quien entra, sale, así que esa diferencia es "
                "del contador. La línea está mal puesta o «la tienda queda» del lado equivocado."
            )
        # Una puerta que no cuenta mientras otra sí.
        de_linea = {c: v for c, v in por_camara.items() if v[0] or v[1]}
        mudas = sorted(c for c, v in por_camara.items() if not (v[0] or v[1]) and not v[2])
        if de_linea and mudas:
            hallazgos.append("Cámaras que no contaron nada en esos días: " + ", ".join(mudas) + ".")

    return Revision(
        hoy=hoy, ultimo_dato=ultimo, dias=revisados,
        por_camara={c: tuple(v) for c, v in sorted(por_camara.items())},
        hallazgos=tuple(hallazgos),
    )


def texto(rev: Revision) -> str:
    """Para Telegram y para la consola."""
    renglones = ["📹 Revisión del contador de personas"]
    if rev.ultimo_dato is not None:
        renglones.append(f"Último dato: {_dia_corto(rev.ultimo_dato.date())} {rev.ultimo_dato:%H:%M}")
    if rev.dias:
        renglones.append("")
        renglones.append("Día · entran / salen · pasan por fuera · ventas · conversión")
        for d in rev.dias:
            conv = f"{d.conversion:.0f}%" if d.conversion is not None else "—"
            renglones.append(
                f"{_dia_corto(d.dia)} · {d.entradas} / {d.salidas} · {d.pasan} · {d.ventas} · {conv}"
            )
    if rev.por_camara:
        renglones.append("")
        renglones.append("Por cámara (entran / salen / pasan):")
        for camara, (e, s, p) in rev.por_camara.items():
            renglones.append(f"• {camara}: {e} / {s} / {p}")
    renglones.append("")
    if rev.hallazgos:
        renglones.append("⚠️ Lo que se ve mal:")
        renglones.extend(f"• {h}" for h in rev.hallazgos)
    else:
        renglones.append(
            "✅ No se ve nada raro: cuenta todos los días, entran y salen cantidades parecidas y "
            "hay más gente que ventas."
        )
        renglones.append(
            "Esto NO prueba que el número sea exacto. Para eso: cuenta a mano quién entra durante "
            "15 minutos y compáralo con esa hora en la Libreta → Afluencia."
        )
    return "\n".join(renglones)
