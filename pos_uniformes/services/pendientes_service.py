"""Pendientes del día para el dueño: lo que hay que registrar y se olvida.

- Pagos que tocan hoy o ya se pasaron y no se han registrado.
- Quién descansa hoy (para no marcarla como falta).
- Posibles faltas: le tocaba trabajar, no tiene movimientos en la Libreta y
  nadie apuntó nada.
- Empleadas sin horario configurado (sin descanso fijo o sin último pago).

`pendientes_del_dia(session, hoy)` lee la base; `texto_pendientes` es puro.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

PAGO_HOY = "pago_hoy"
PAGO_ATRASADO = "pago_atrasado"
DESCANSO_HOY = "descanso_hoy"
POSIBLE_FALTA = "posible_falta"
SIN_HORARIO = "sin_horario"

# Antes de esta hora no se sugieren faltas (todavía puede llegar / vender).
HORA_MINIMA_FALTA = 13


@dataclass(frozen=True)
class Pendiente:
    tipo: str
    employee_code: str
    employee_name: str
    texto: str
    monto: Decimal | None = None
    dias: int | None = None

    @property
    def nombre_corto(self) -> str:
        return (self.employee_name or self.employee_code).split()[0]


def _orden(p: Pendiente) -> tuple:
    prioridad = {PAGO_ATRASADO: 0, PAGO_HOY: 1, POSIBLE_FALTA: 2, SIN_HORARIO: 3, DESCANSO_HOY: 4}
    return (prioridad.get(p.tipo, 9), p.employee_name)


def pendientes_del_dia(session, hoy: date | None = None, ahora: datetime | None = None) -> list[Pendiente]:
    from pos_uniformes.database.models import Empleada, LibretaVenta
    from pos_uniformes.services.calendario_empleadas_service import (
        DESCANSO,
        TRABAJO,
        cargar_horario,
        estado_del_dia,
    )
    from pos_uniformes.services.libreta_service import ventana_hoy
    from pos_uniformes.services.nomina_service import QUIEN_PUEDE_PAGAR, avisos_de_pago

    hoy = hoy or date.today()
    ahora = ahora or datetime.now()
    salida: list[Pendiente] = []

    empleadas = [
        e for e in session.query(Empleada).filter(Empleada.activo.is_(True)).order_by(Empleada.nombre_completo).all()
        if e.codigo.upper() not in QUIEN_PUEDE_PAGAR
    ]
    horarios = {e.codigo.upper(): cargar_horario(session, e.codigo) for e in empleadas}

    # Pagos de hoy / atrasados (sin registrar hoy). Defensivo: si la base
    # aún no tiene las tablas de nómina, se omite este bloque.
    try:
        avisos = avisos_de_pago(session, hoy, dias=0)
    except Exception:  # noqa: BLE001
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass
        avisos = []
    for a in avisos:
        if a.dias_para_pago is None or a.dias_para_pago > 0:
            continue
        h = horarios.get(a.employee_code)
        if h is not None and h.fecha_ultimo_pago == hoy:
            continue
        nombre = a.employee_name.split()[0]
        if a.dias_para_pago < 0:
            salida.append(Pendiente(
                PAGO_ATRASADO, a.employee_code, a.employee_name,
                f"Pago de {nombre} atrasado {-a.dias_para_pago} día(s): ${a.total_estimado:,.2f}",
                monto=a.total_estimado, dias=a.dias_para_pago,
            ))
        else:
            salida.append(Pendiente(
                PAGO_HOY, a.employee_code, a.employee_name,
                f"Hoy toca pagar a {nombre}: ${a.total_estimado:,.2f} ({a.comisiones} com.)",
                monto=a.total_estimado, dias=0,
            ))

    # Movimientos de hoy por empleada (para sugerir faltas).
    desde, hasta = ventana_hoy(hoy)
    con_movimientos = {
        code.upper()
        for (code,) in session.query(LibretaVenta.employee_code)
        .filter(LibretaVenta.created_at >= desde, LibretaVenta.created_at <= hasta)
        .distinct()
        .all()
    }
    sugerir_faltas = ahora.hour >= HORA_MINIMA_FALTA

    for e in empleadas:
        code = e.codigo.upper()
        h = horarios[code]
        nombre = e.nombre_completo.split()[0]
        if not h.configurado or (not h.por_dia and h.fecha_ultimo_pago is None):
            que = []
            if not h.configurado:
                que.append("días de trabajo" if h.por_dia else "descanso fijo")
            if not h.por_dia and h.fecha_ultimo_pago is None:
                que.append("fecha del último pago")
            salida.append(Pendiente(SIN_HORARIO, code, e.nombre_completo, f"{nombre} no tiene {' ni '.join(que)} configurado"))
        estado = estado_del_dia(h, hoy)
        if estado == DESCANSO:
            salida.append(Pendiente(DESCANSO_HOY, code, e.nombre_completo, f"{nombre} descansa hoy"))
        elif (
            estado == TRABAJO
            and h.configurado  # sin horario no se adivina nada
            and sugerir_faltas
            and code not in con_movimientos
            and hoy not in h.eventos
        ):
            salida.append(Pendiente(POSIBLE_FALTA, code, e.nombre_completo, f"{nombre} no tiene movimientos hoy. ¿Faltó?"))

    salida.sort(key=_orden)
    return salida


def texto_pendientes(pendientes: list[Pendiente]) -> str:
    """Bloque para Telegram / pantalla. Vacío si no hay nada que hacer."""
    accion = [p for p in pendientes if p.tipo in (PAGO_HOY, PAGO_ATRASADO, POSIBLE_FALTA, SIN_HORARIO)]
    descansos = [p for p in pendientes if p.tipo == DESCANSO_HOY]
    if not accion and not descansos:
        return ""
    lineas = ["📌 PENDIENTES"]
    for p in accion:
        icono = {PAGO_ATRASADO: "❗", PAGO_HOY: "💵", POSIBLE_FALTA: "❓", SIN_HORARIO: "⚙️"}[p.tipo]
        lineas.append(f"{icono} {p.texto}")
    if descansos:
        lineas.append("🛌 Descansa hoy: " + ", ".join(p.nombre_corto for p in descansos))
    return "\n".join(lineas)
