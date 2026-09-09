"""Resumen diario del negocio (para mandarlo por Telegram al cierre).

Junta en un solo texto lo que el sistema ya calcula: ventas del día,
cortes (con sobrante/faltante), pagos a empleadas, faltas, afluencia y
conversión de las cámaras, y qué viene mañana (descansos y pagos).

`recolectar(session, hoy)` lee la base; `formatear(datos)` es puro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

_CENT = Decimal("0.01")
_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


@dataclass(frozen=True)
class CorteResumen:
    hora: str
    creado_por: str
    contado: Decimal
    esperado: Decimal
    reactivo_final: Decimal
    retiros_pagos: Decimal
    otros_retiros: Decimal

    @property
    def diferencia(self) -> Decimal:
        return (self.contado - self.esperado).quantize(_CENT)


@dataclass(frozen=True)
class PagoResumen:
    nombre: str
    total: Decimal
    comisiones: int
    faltas: int


@dataclass
class DatosResumen:
    fecha: date
    operaciones: int = 0
    piezas: int = 0
    ventas: Decimal = Decimal("0.00")
    abonos: Decimal = Decimal("0.00")
    apartados: Decimal = Decimal("0.00")
    efectivo: Decimal = Decimal("0.00")
    tarjeta: Decimal = Decimal("0.00")
    por_empleada: list[tuple[str, int, int]] = field(default_factory=list)  # (nombre, operaciones, comisiones)
    cortes: list[CorteResumen] = field(default_factory=list)
    horas_sin_corte: float | None = None  # desde el último corte (None = nunca)
    pagos: list[PagoResumen] = field(default_factory=list)
    faltaron: list[str] = field(default_factory=list)
    afluencia_entradas: int | None = None
    afluencia_pasan: int | None = None
    afluencia_ventas: int | None = None
    descansan_manana: list[str] = field(default_factory=list)
    pagos_proximos: list[tuple[str, str, Decimal]] = field(default_factory=list)  # (nombre, cuándo, total)
    pendientes: str = ""  # bloque de pendientes_service.texto_pendientes (ya formateado)
    retiros: list[tuple[str, Decimal, str]] = field(default_factory=list)  # (motivo, monto, quién)


def _pesos(v: Decimal) -> str:
    return f"${Decimal(v):,.2f}"


def formatear(d: DatosResumen) -> str:
    """Texto listo para Telegram (sin markdown, para que nada se rompa)."""
    fecha = f"{_DIAS[d.fecha.weekday()]} {d.fecha:%d/%m/%Y}"
    lineas = [f"📒 RESUMEN DEL DÍA · {fecha}", ""]

    lineas.append("💰 VENTAS")
    if d.operaciones:
        lineas.append(f"• {d.operaciones} operaciones · {d.piezas} piezas")
        lineas.append(f"• Ventas: {_pesos(d.ventas)}")
        if d.abonos:
            lineas.append(f"• Abonos: {_pesos(d.abonos)}")
        if d.apartados:
            lineas.append(f"• Apartados nuevos: {_pesos(d.apartados)} (comprometido)")
        lineas.append(f"• Efectivo: {_pesos(d.efectivo)} · Tarjeta: {_pesos(d.tarjeta)}")
        if d.por_empleada:
            lineas.append("• Por empleada: " + ", ".join(f"{n} {o} ops/{c} com." for n, o, c in d.por_empleada))
    else:
        lineas.append("• Sin operaciones registradas hoy.")
    lineas.append("")

    lineas.append("🧾 CORTES")
    if d.cortes:
        for c in d.cortes:
            dif = c.diferencia
            if str(c.creado_por or "").upper() == "VEND-1":
                estado = "cifra del dueño"  # su corte no deja rastro de diferencia
            elif dif == 0:
                estado = "cuadró exacto ✅"
            elif dif > 0:
                estado = f"sobraron {_pesos(dif)} ⚠️"
            else:
                estado = f"FALTARON {_pesos(-dif)} ❗"
            lineas.append(f"• {c.hora} por {c.creado_por}: en caja {_pesos(c.contado)} · {estado}")
            extras = [f"fondo que queda {_pesos(c.reactivo_final)}"]
            if c.retiros_pagos:
                extras.append(f"pagos {_pesos(c.retiros_pagos)}")
            if c.otros_retiros:
                extras.append(f"otros retiros {_pesos(c.otros_retiros)}")
            lineas.append("   " + " · ".join(extras))
    else:
        if d.horas_sin_corte is None:
            lineas.append("• Sin corte hoy (nunca se ha hecho uno).")
        elif d.horas_sin_corte >= 24:
            lineas.append(f"• ❗ SIN CORTE HOY. El último fue hace {d.horas_sin_corte / 24:.1f} días.")
        else:
            lineas.append("• Sin corte hoy.")
    lineas.append("")

    if d.retiros:
        lineas.append("💸 RETIROS DEL CAJÓN")
        for motivo, monto, quien in d.retiros:
            lineas.append(f"• {motivo}: {_pesos(monto)} ({quien})")
        lineas.append(f"• Total: {_pesos(sum((m for _, m, _ in d.retiros), Decimal('0.00')))}")
        lineas.append("")

    if d.pagos or d.faltaron:
        lineas.append("👥 EMPLEADAS")
        for p in d.pagos:
            detalle = f"{p.comisiones} com."
            if p.faltas:
                detalle += f", {p.faltas} falta(s) descontada(s)"
            lineas.append(f"• Pagado a {p.nombre}: {_pesos(p.total)} ({detalle})")
        if d.faltaron:
            lineas.append("• Faltaron hoy: " + ", ".join(d.faltaron))
        lineas.append("")

    if d.afluencia_entradas is not None:
        lineas.append("🚶 AFLUENCIA (cámaras)")
        entradas = d.afluencia_entradas or 0
        ventas = d.afluencia_ventas or 0
        conv = f"{100.0 * ventas / entradas:.0f}%" if entradas else "—"
        lineas.append(f"• Entraron {entradas} personas · pasaron por fuera {d.afluencia_pasan or 0}")
        lineas.append(f"• Compraron {ventas} → conversión {conv}")
        lineas.append("")

    if d.pendientes:
        lineas.append(d.pendientes)
        lineas.append("")

    lineas.append("📅 MAÑANA")
    lineas.append("• Descansa: " + (", ".join(d.descansan_manana) or "nadie"))
    if d.pagos_proximos:
        lineas.append("• Pagos: " + " | ".join(f"{n} {cuando} {_pesos(t)}" for n, cuando, t in d.pagos_proximos))
    return "\n".join(lineas).rstrip()


# ─── Acceso a datos ──────────────────────────────────────────────────────

def recolectar(session, hoy: date | None = None) -> DatosResumen:
    """Lee todo lo del día. Cada bloque es defensivo: si una tabla no existe
    (base sin migrar) ese bloque se omite y el resto sale igual."""
    from pos_uniformes.services.corte_caja_service import resumir_periodo
    from pos_uniformes.services.libreta_service import listar_operaciones, resumir_por_empleada, ventana_hoy

    hoy = hoy or date.today()
    desde, hasta = ventana_hoy(hoy)
    d = DatosResumen(fecha=hoy)

    rows = listar_operaciones(session, desde=desde, hasta=hasta)
    r = resumir_periodo(rows)
    d.operaciones, d.piezas = r.operaciones, r.piezas
    d.ventas, d.abonos, d.apartados, d.efectivo, d.tarjeta = r.ventas, r.abonos, r.apartados, r.efectivo, r.tarjeta
    d.por_empleada = [
        ((e.employee_name or e.employee_code).split()[0], e.operaciones, e.comisiones)
        for e in resumir_por_empleada(rows)
    ]

    _bloque(session, lambda: _cortes(session, d, hoy))
    _bloque(session, lambda: _pagos(session, d, desde, hasta))
    _bloque(session, lambda: _faltas(session, d, hoy))
    _bloque(session, lambda: _afluencia(session, d, desde, hasta))
    _bloque(session, lambda: _manana(session, d, hoy))
    _bloque(session, lambda: _pendientes(session, d, hoy))
    _bloque(session, lambda: _retiros(session, d, desde, hasta))
    return d


def _retiros(session, d: DatosResumen, desde: datetime, hasta: datetime) -> None:
    from pos_uniformes.services.retiros_service import retiros_del_periodo

    d.retiros = [(r.motivo, Decimal(r.monto), r.creado_por) for r in retiros_del_periodo(session, desde - timedelta(seconds=1), hasta)]


def _pendientes(session, d: DatosResumen, hoy: date) -> None:
    from pos_uniformes.services.pendientes_service import pendientes_del_dia, texto_pendientes

    d.pendientes = texto_pendientes(pendientes_del_dia(session, hoy))


def texto_solo_pendientes(session, hoy: date | None = None) -> str:
    """Recordatorio de mediodía: solo lo que falta por registrar."""
    from pos_uniformes.services.pendientes_service import pendientes_del_dia, texto_pendientes

    hoy = hoy or date.today()
    texto = texto_pendientes(pendientes_del_dia(session, hoy))
    if not texto:
        return ""
    return f"{_DIAS[hoy.weekday()]} {hoy:%d/%m}\n{texto}"


def _bloque(session, fn) -> None:
    try:
        fn()
    except Exception:  # noqa: BLE001
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass


def _cortes(session, d: DatosResumen, hoy: date) -> None:
    from pos_uniformes.database.models import LibretaCorte

    filas = (
        session.query(LibretaCorte)
        .filter(LibretaCorte.fecha == hoy)
        .order_by(LibretaCorte.id)
        .all()
    )
    for c in filas:
        momento = c.hasta or c.created_at
        momento = momento.astimezone() if momento.tzinfo else momento
        d.cortes.append(
            CorteResumen(
                hora=momento.strftime("%H:%M"),
                creado_por=str(c.creado_por or ""),
                contado=Decimal(c.monto_final),
                esperado=Decimal(c.monto_esperado or 0),
                reactivo_final=Decimal(c.reactivo_final or 0),
                retiros_pagos=Decimal(c.retiros_pagos or 0),
                otros_retiros=Decimal(c.otros_retiros or 0),
            )
        )
    if not filas:
        ultimo = session.query(LibretaCorte).order_by(LibretaCorte.id.desc()).first()
        if ultimo is not None:
            momento = ultimo.hasta or ultimo.created_at
            ahora = datetime.now(momento.tzinfo) if momento.tzinfo else datetime.now()
            d.horas_sin_corte = (ahora - momento).total_seconds() / 3600


def _pagos(session, d: DatosResumen, desde: datetime, hasta: datetime) -> None:
    from pos_uniformes.database.models import EmpleadaPago

    filas = (
        session.query(EmpleadaPago)
        .filter(EmpleadaPago.created_at >= desde, EmpleadaPago.created_at <= hasta)
        .order_by(EmpleadaPago.id)
        .all()
    )
    d.pagos = [
        PagoResumen(
            nombre=(p.employee_name or p.employee_code).split()[0],
            total=Decimal(p.total),
            comisiones=int(p.comisiones or 0),
            faltas=int(p.faltas or 0),
        )
        for p in filas
    ]


def _faltas(session, d: DatosResumen, hoy: date) -> None:
    from pos_uniformes.database.models import Empleada, EmpleadaEvento
    from pos_uniformes.services.calendario_empleadas_service import FALTA

    nombres = {e.codigo.upper(): e.nombre_completo.split()[0] for e in session.query(Empleada).all()}
    filas = session.query(EmpleadaEvento).filter(EmpleadaEvento.fecha == hoy, EmpleadaEvento.tipo == FALTA).all()
    d.faltaron = [nombres.get(f.employee_code.upper(), f.employee_code) for f in filas]


def _afluencia(session, d: DatosResumen, desde: datetime, hasta: datetime) -> None:
    from pos_uniformes.services.afluencia_service import resumen_afluencia, totales

    filas = [f for f in resumen_afluencia(session, desde=desde, hasta=hasta) if f.hora.date() == d.fecha]
    t = totales(filas)
    if t is None or not (t.entradas or t.pasan):
        return
    d.afluencia_entradas, d.afluencia_pasan, d.afluencia_ventas = t.entradas, t.pasan, t.ventas


def _manana(session, d: DatosResumen, hoy: date) -> None:
    from pos_uniformes.services.nomina_service import avisos_de_pago, resumen_para_encargado

    r = resumen_para_encargado(session, hoy)
    d.descansan_manana = [n.split()[0] for n in r.descansan_manana]
    proximos = []
    for a in avisos_de_pago(session, hoy, dias=7):
        if a.dias_para_pago is None:
            cuando = "sin fecha"
        elif a.dias_para_pago < 0:
            cuando = f"ATRASADO {-a.dias_para_pago}d"
        elif a.dias_para_pago == 0:
            cuando = "hoy (pendiente)"
        elif a.dias_para_pago == 1:
            cuando = "mañana"
        else:
            cuando = _DIAS[a.fecha_pago.weekday()] if a.fecha_pago else ""
        proximos.append((a.employee_name.split()[0], cuando, a.total_estimado))
    d.pagos_proximos = proximos
