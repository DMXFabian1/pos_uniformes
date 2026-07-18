"""Recordatorios del calendario: pagos, descansos y notas.

Cada recordatorio es en una fecha específica (recurrencia='unica') o se repite
cada mes (día del mes) o cada semana (día de la semana). Las funciones de
expansión son puras (reciben la lista) para poder probarlas sin base de datos.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Recordatorio

TIPOS = ("pago", "descanso", "nota")
RECURRENCIAS = ("unica", "mensual", "semanal")

# Etiqueta e ícono por tipo, para la UI.
TIPO_LABEL = {"pago": "Pago", "descanso": "Descanso", "nota": "Nota"}
TIPO_ICONO = {"pago": "💲", "descanso": "🌴", "nota": "📌"}


# ── Ocurrencia / expansión (puro) ──────────────────────────────────────────

def _ultimo_dia_mes(anio: int, mes: int) -> int:
    return calendar.monthrange(anio, mes)[1]


def ocurre_en(recordatorio: Recordatorio, dia: date) -> bool:
    """True si el recordatorio cae en esa fecha (según su recurrencia)."""
    if not recordatorio.activo:
        return False
    if recordatorio.recurrencia == "unica":
        return recordatorio.fecha == dia
    if recordatorio.recurrencia == "mensual":
        if recordatorio.dia_mes is None:
            return False
        # "día 31" en un mes de 30 cae el último día (útil para pagos de fin de mes).
        objetivo = min(recordatorio.dia_mes, _ultimo_dia_mes(dia.year, dia.month))
        return dia.day == objetivo
    if recordatorio.recurrencia == "semanal":
        return recordatorio.dia_semana is not None and dia.weekday() == recordatorio.dia_semana
    return False


def recordatorios_del_mes(
    recordatorios: list[Recordatorio], anio: int, mes: int
) -> dict[int, list[Recordatorio]]:
    """{día_del_mes: [recordatorios]} para pintar el calendario del mes."""
    por_dia: dict[int, list[Recordatorio]] = {}
    for d in range(1, _ultimo_dia_mes(anio, mes) + 1):
        fecha = date(anio, mes, d)
        ocurren = [r for r in recordatorios if ocurre_en(r, fecha)]
        if ocurren:
            por_dia[d] = ocurren
    return por_dia


def proximos_recordatorios(
    recordatorios: list[Recordatorio], hoy: date, dias: int = 7
) -> list[tuple[date, Recordatorio]]:
    """(fecha, recordatorio) desde hoy hasta hoy+dias (incluidos), en orden."""
    resultado: list[tuple[date, Recordatorio]] = []
    for i in range(dias + 1):
        fecha = hoy + timedelta(days=i)
        for r in recordatorios:
            if ocurre_en(r, fecha):
                resultado.append((fecha, r))
    return resultado


# ── CRUD ───────────────────────────────────────────────────────────────────

def listar_recordatorios(session: Session, *, solo_activos: bool = True) -> list[Recordatorio]:
    stmt = select(Recordatorio).order_by(Recordatorio.titulo)
    if solo_activos:
        stmt = stmt.where(Recordatorio.activo.is_(True))
    return list(session.scalars(stmt).all())


def _validar_y_normalizar(
    *, tipo, titulo, recurrencia, fecha, dia_mes, dia_semana, monto, notas
) -> dict:
    """Valida y devuelve los campos limpios (compartido por crear/actualizar)."""
    if tipo not in TIPOS:
        raise ValueError(f"Tipo inválido: {tipo!r}")
    if recurrencia not in RECURRENCIAS:
        raise ValueError(f"Recurrencia inválida: {recurrencia!r}")
    titulo = (titulo or "").strip()
    if not titulo:
        raise ValueError("El recordatorio necesita un título.")

    if recurrencia == "unica" and fecha is None:
        raise ValueError("Un recordatorio de fecha específica necesita la fecha.")
    if recurrencia == "mensual":
        if dia_mes is None or not (1 <= dia_mes <= 31):
            raise ValueError("El recordatorio mensual necesita un día del mes (1–31).")
    if recurrencia == "semanal":
        if dia_semana is None or not (0 <= dia_semana <= 6):
            raise ValueError("El recordatorio semanal necesita un día de la semana (0–6).")

    return dict(
        tipo=tipo,
        titulo=titulo,
        recurrencia=recurrencia,
        fecha=fecha if recurrencia == "unica" else None,
        dia_mes=dia_mes if recurrencia == "mensual" else None,
        dia_semana=dia_semana if recurrencia == "semanal" else None,
        monto=Decimal(str(monto)) if monto not in (None, "") else None,
        notas=(notas or "").strip() or None,
    )


def crear_recordatorio(
    session: Session,
    *,
    tipo: str,
    titulo: str,
    recurrencia: str = "unica",
    fecha: date | None = None,
    dia_mes: int | None = None,
    dia_semana: int | None = None,
    monto: Decimal | float | None = None,
    notas: str | None = None,
) -> Recordatorio:
    """Crea un recordatorio validando el tipo, la recurrencia y su fecha/día."""
    datos = _validar_y_normalizar(
        tipo=tipo, titulo=titulo, recurrencia=recurrencia, fecha=fecha,
        dia_mes=dia_mes, dia_semana=dia_semana, monto=monto, notas=notas,
    )
    rec = Recordatorio(**datos)
    session.add(rec)
    session.flush()
    return rec


def actualizar_recordatorio(
    session: Session,
    recordatorio_id: int,
    *,
    tipo: str,
    titulo: str,
    recurrencia: str = "unica",
    fecha: date | None = None,
    dia_mes: int | None = None,
    dia_semana: int | None = None,
    monto: Decimal | float | None = None,
    notas: str | None = None,
) -> Recordatorio:
    """Actualiza un recordatorio existente (mismas validaciones que crear)."""
    rec = session.get(Recordatorio, recordatorio_id)
    if rec is None:
        raise ValueError("El recordatorio ya no existe.")
    datos = _validar_y_normalizar(
        tipo=tipo, titulo=titulo, recurrencia=recurrencia, fecha=fecha,
        dia_mes=dia_mes, dia_semana=dia_semana, monto=monto, notas=notas,
    )
    for campo, valor in datos.items():
        setattr(rec, campo, valor)
    session.flush()
    return rec


def eliminar_recordatorio(session: Session, recordatorio_id: int) -> None:
    """Elimina (borra) un recordatorio."""
    rec = session.get(Recordatorio, recordatorio_id)
    if rec is not None:
        session.delete(rec)


def eliminar_recordatorios_vencidos(session: Session, hoy: date) -> int:
    """Borra los de fecha específica ya pasada. Devuelve cuántos borró.

    Los recurrentes (mensual/semanal) nunca "vencen": no se tocan.
    """
    vencidos = list(
        session.scalars(
            select(Recordatorio).where(
                Recordatorio.recurrencia == "unica",
                Recordatorio.fecha.is_not(None),
                Recordatorio.fecha < hoy,
            )
        ).all()
    )
    for r in vencidos:
        session.delete(r)
    return len(vencidos)
