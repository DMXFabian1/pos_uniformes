"""Lista de asistencia del equipo, para el bot de Telegram.

Nadie checa entrada: la presencia se **deduce** del primer movimiento del día
en la Libreta (una venta, un apartado, un abono) o de una jornada de conteo
abierta. Por eso el mensaje distingue "vino" de "sin señal todavía": una
empleada puede estar en el piso y no haber vendido aún.

Lo que sí es dato duro: el descanso (fijo o marcado) y la falta que marcó
León o Daniel en el calendario.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

PRESENTE = "presente"
SIN_SENAL = "sin_senal"
DESCANSO = "descanso"
FALTA = "falta"

_ICONO = {PRESENTE: "✅", SIN_SENAL: "⏳", DESCANSO: "🛌", FALTA: "✗"}
_DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")


@dataclass(frozen=True)
class Asistencia:
    code: str
    nombre: str
    estado: str
    primera_senal: datetime | None = None   # hora local del primer movimiento
    movimientos: int = 0
    nota: str = ""                          # p.ej. "marcada por León"
    confirmado: bool = False                # Daniel dijo "vino"/"falta" (manda sobre lo deducido)

    @property
    def nombre_corto(self) -> str:
        return self.nombre.split()[0] if self.nombre else self.code


def _local(momento: datetime) -> datetime:
    """Postgres devuelve con zona → a hora local. SQLite (tests) devuelve sin
    zona y ya es hora local: se deja como está (igual que analitica_libreta)."""
    if momento.tzinfo is None:
        return momento
    return momento.astimezone().replace(tzinfo=None)


def clasificar(*, estado_dia: str, movimientos: int, primera: datetime | None, confirmado_trabajo: bool = False) -> str:
    """Puro: del estado del calendario y la actividad, el estado de asistencia.

    `confirmado_trabajo`: Daniel marcó "vino" en el calendario; vale aunque
    no haya vendido nada todavía."""
    from pos_uniformes.services.calendario_empleadas_service import DESCANSO as C_DESCANSO
    from pos_uniformes.services.calendario_empleadas_service import FALTA as C_FALTA

    if estado_dia == C_FALTA:
        return FALTA
    if estado_dia == C_DESCANSO:
        return DESCANSO
    if confirmado_trabajo:
        return PRESENTE
    return PRESENTE if (movimientos > 0 or primera is not None) else SIN_SENAL


def asistencia_del_dia(session, hoy: date | None = None) -> list[Asistencia]:
    from sqlalchemy import func, select

    from pos_uniformes.database.models import ConteoJornada, Empleada, LibretaVenta
    from pos_uniformes.services.calendario_empleadas_service import TRABAJO as C_TRABAJO
    from pos_uniformes.services.calendario_empleadas_service import cargar_horario, estado_del_dia
    from pos_uniformes.services.libreta_service import ventana_hoy
    from pos_uniformes.services.nomina_service import QUIEN_PUEDE_PAGAR

    hoy = hoy or date.today()
    desde, hasta = ventana_hoy(hoy)

    empleadas = [
        e for e in session.scalars(
            select(Empleada).where(Empleada.activo.is_(True)).order_by(Empleada.nombre_completo)
        ).all()
        if e.codigo.upper() not in QUIEN_PUEDE_PAGAR
    ]

    # Primer movimiento y cuántos, por empleada, en la Libreta de hoy.
    filas = session.execute(
        select(LibretaVenta.employee_code, func.min(LibretaVenta.created_at), func.count())
        .where(LibretaVenta.created_at >= desde, LibretaVenta.created_at <= hasta)
        .group_by(LibretaVenta.employee_code)
    ).all()
    actividad = {str(c).upper(): (_local(m), int(n)) for c, m, n in filas if c}

    # Una jornada de conteo abierta hoy también es presencia.
    try:
        jornadas = session.execute(
            select(ConteoJornada.empleada_code, func.min(ConteoJornada.iniciada_at))
            .where(ConteoJornada.iniciada_at >= desde, ConteoJornada.iniciada_at <= hasta)
            .group_by(ConteoJornada.empleada_code)
        ).all()
    except Exception:  # noqa: BLE001 — base sin la tabla todavía
        session.rollback()
        jornadas = []
    for c, m in jornadas:
        code = str(c).upper()
        primera, n = actividad.get(code, (None, 0))
        m_local = _local(m)
        actividad[code] = (m_local if primera is None or m_local < primera else primera, n)

    salida: list[Asistencia] = []
    for e in empleadas:
        code = e.codigo.upper()
        horario = cargar_horario(session, e.codigo)
        estado_dia = estado_del_dia(horario, hoy)
        primera, n = actividad.get(code, (None, 0))
        marcado = hoy in horario.eventos
        confirmado_trabajo = marcado and horario.eventos.get(hoy) == C_TRABAJO
        estado = clasificar(
            estado_dia=estado_dia, movimientos=n, primera=primera, confirmado_trabajo=confirmado_trabajo
        )
        nota = ""
        if marcado and estado in (FALTA, DESCANSO, PRESENTE):
            nota = _nota_de(session, code, hoy)
        salida.append(Asistencia(code, e.nombre_completo, estado, primera, n, nota, confirmado=marcado))
    orden = {PRESENTE: 0, SIN_SENAL: 1, FALTA: 2, DESCANSO: 3}
    return sorted(salida, key=lambda a: (orden[a.estado], a.primera_senal or datetime.max, a.nombre))


def texto_asistencia(lista: list[Asistencia], hoy: date | None = None, ahora: datetime | None = None) -> str:
    """El mensaje, puro."""
    hoy = hoy or date.today()
    ahora = ahora or datetime.now()
    lineas = [f"👥 Asistencia · {_DIAS[hoy.weekday()]} {hoy:%d/%m} · {ahora:%H:%M}"]
    if not lista:
        lineas.append("No hay empleadas activas.")
        return "\n".join(lineas)
    for a in lista:
        icono = _ICONO[a.estado]
        sello = f" ({a.nota})" if a.nota else ""
        if a.estado == PRESENTE:
            hora = f" desde {a.primera_senal:%H:%M}" if a.primera_senal else ""
            movs = f" · {a.movimientos} mov." if a.movimientos else ""
            base = f"{hora}{movs}".strip() or " vino"
            lineas.append(f"{icono} {a.nombre_corto} — {base.strip()}{sello}")
        elif a.estado == SIN_SENAL:
            lineas.append(f"{icono} {a.nombre_corto} — sin movimientos todavía")
        elif a.estado == FALTA:
            lineas.append(f"{icono} {a.nombre_corto} — falta{sello}")
        else:
            lineas.append(f"{icono} {a.nombre_corto} — descansa{sello}")
    cuenta = {k: sum(1 for a in lista if a.estado == k) for k in (PRESENTE, SIN_SENAL, DESCANSO, FALTA)}
    partes = [f"{cuenta[PRESENTE]} presentes"]
    if cuenta[SIN_SENAL]:
        partes.append(f"{cuenta[SIN_SENAL]} sin señal")
    if cuenta[DESCANSO]:
        partes.append(f"{cuenta[DESCANSO]} descanso")
    if cuenta[FALTA]:
        partes.append(f"{cuenta[FALTA]} falta")
    lineas.append("—")
    lineas.append(f"{len(lista)} activas · " + " · ".join(partes))
    lineas.append("Presencia = primer movimiento en la Libreta o un conteo abierto.")
    comandos = comandos_asistencia(lista)
    if comandos:
        lineas.append("")
        lineas.append("Marcar (toca uno; repetir lo quita):")
        lineas.append(comandos)
    return "\n".join(lineas)


def token_nombre(a: Asistencia, lista: list[Asistencia] | None = None) -> str:
    """El nombre como va en el comando: sin acentos ni espacios, para que
    Telegram lo vuelva tocable. Si dos se llaman igual, se agrega la inicial
    del apellido."""
    import unicodedata

    def _limpio(texto: str) -> str:
        sin = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
        return "".join(ch for ch in sin if ch.isalnum())

    nombre = _limpio(a.nombre_corto)
    repetido = lista is not None and sum(1 for o in lista if _limpio(o.nombre_corto).lower() == nombre.lower()) > 1
    if repetido:
        partes = a.nombre.split()
        if len(partes) > 1:
            nombre += _limpio(partes[1])[:1].upper()
    return nombre or a.code.replace("-", "")


def comandos_asistencia(lista: list[Asistencia]) -> str:
    """Una línea por empleada con sus comandos tocables (puro)."""
    lineas = []
    for a in lista:
        t = token_nombre(a, lista)
        marca_f = "✗ " if a.estado == FALTA and a.confirmado else ""
        marca_d = "🛌 " if a.estado == DESCANSO and a.confirmado else ""
        lineas.append(f"{marca_f}/falta_{t} · {marca_d}/descanso_{t}")
    return "\n".join(lineas)


def _nota_de(session, code: str, dia: date) -> str:
    """De dónde salió la marca del calendario ('tú', 'León'…)."""
    from sqlalchemy import select

    from pos_uniformes.database.models import EmpleadaEvento

    ev = session.scalar(
        select(EmpleadaEvento).where(EmpleadaEvento.employee_code == code, EmpleadaEvento.fecha == dia)
    )
    nota = str(getattr(ev, "nota", "") or "")
    if nota.startswith(NOTA_TELEGRAM):
        return "tú"
    return nota or "marcado en el calendario"


# ── Marcar desde Telegram ───────────────────────────────────────────────
NOTA_TELEGRAM = "Daniel desde Telegram"
VINO, NO_VINO, DESCANSA = "vino", "falta", "descanso"
_PREFIJO = "asis"


def teclado_asistencia(lista: list[Asistencia]) -> list[list[tuple[str, str]]]:
    """Una fila por empleada: [nombre ☐ faltó] [☐ descanso] (puro).

    Que vino ya lo deduce el sistema; lo que Daniel tiene que decir es la
    excepción: faltó, o descansa hoy. Tocar de nuevo el botón marcado quita
    la marca (vuelve a lo deducido). El dato del botón es "asis:<code>:<accion>".
    """
    filas = []
    for a in lista:
        marca_f = "✗" if a.estado == FALTA and a.confirmado else "☐"
        marca_d = "🛌" if a.estado == DESCANSO and a.confirmado else "☐"
        filas.append([
            (f"{marca_f} {a.nombre_corto} faltó", f"{_PREFIJO}:{a.code}:{NO_VINO}"),
            (f"{marca_d} descanso", f"{_PREFIJO}:{a.code}:{DESCANSA}"),
        ])
    return filas


def interpretar_toque(dato: str) -> tuple[str, str] | None:
    """'asis:VEND-4:vino' → ('VEND-4', 'vino'). None si no es nuestro (puro)."""
    partes = (dato or "").split(":")
    if len(partes) != 3 or partes[0] != _PREFIJO or partes[2] not in (VINO, NO_VINO, DESCANSA):
        return None
    return partes[1].strip().upper(), partes[2]


def marcar(session, code: str, accion: str, hoy: date | None = None) -> str:
    """Escribe la palabra de Daniel en el calendario (el mismo que usa León).

    'vino' → TRABAJO, 'falta' → FALTA, 'descanso' → DESCANSO. Devuelve el
    texto corto para confirmar en el celular."""
    from pos_uniformes.database.models import Empleada
    from pos_uniformes.services.calendario_empleadas_service import DESCANSO as C_DESCANSO
    from pos_uniformes.services.calendario_empleadas_service import FALTA as C_FALTA
    from pos_uniformes.services.calendario_empleadas_service import TRABAJO as C_TRABAJO
    from pos_uniformes.services.calendario_empleadas_service import marcar_dia
    from sqlalchemy import select

    from pos_uniformes.services.calendario_empleadas_service import cargar_horario, quitar_marca

    hoy = hoy or date.today()
    code = (code or "").strip().upper()
    emp = session.scalar(select(Empleada).where(Empleada.codigo == code, Empleada.activo.is_(True)))
    if emp is None:
        return f"No conozco el gafete {code}."
    nombre = emp.nombre_completo.split()[0]
    tipo = {VINO: C_TRABAJO, NO_VINO: C_FALTA, DESCANSA: C_DESCANSO}[accion]
    # Mismo botón dos veces = quitar la marca: vuelve a lo que el sistema deduce.
    if cargar_horario(session, code).eventos.get(hoy) == tipo:
        quitar_marca(session, code, hoy)
        return f"{nombre}: marca quitada ↩"
    marcar_dia(session, code, hoy, tipo, nota=NOTA_TELEGRAM)
    return {VINO: f"{nombre}: vino ✅", NO_VINO: f"{nombre}: falta ✗", DESCANSA: f"{nombre}: descansa 🛌"}[accion]


def buscar_code(session, nombre: str) -> str | None:
    """'/vino fanny' → el gafete de la única activa cuyo nombre empiece así."""
    from sqlalchemy import select

    from pos_uniformes.database.models import Empleada
    from pos_uniformes.services.nomina_service import QUIEN_PUEDE_PAGAR

    import unicodedata

    def _plano(texto: str) -> str:
        sin = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
        return "".join(ch for ch in sin if ch.isalnum()).lower()

    pista = _plano(nombre)
    if not pista:
        return None
    activas = [
        e for e in session.scalars(select(Empleada).where(Empleada.activo.is_(True))).all()
        if e.codigo.upper() not in QUIEN_PUEDE_PAGAR
    ]
    por_gafete = [e for e in activas if _plano(e.codigo) == pista]
    if len(por_gafete) == 1:
        return por_gafete[0].codigo.upper()
    # "FannyO" (nombre + inicial del apellido, cuando dos se llaman igual)
    # o "Fanny" (prefijo del nombre completo sin espacios).
    candidatas = [e for e in activas if _plano(e.nombre_completo).startswith(pista)]
    if len(candidatas) != 1:
        partes_iguales = [
            e for e in activas
            if _plano(e.nombre_completo.split()[0]) + _plano(" ".join(e.nombre_completo.split()[1:2]))[:1] == pista
        ]
        candidatas = partes_iguales if len(partes_iguales) == 1 else candidatas
    return candidatas[0].codigo.upper() if len(candidatas) == 1 else None
