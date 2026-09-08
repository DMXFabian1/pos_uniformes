"""Horario de la tienda y hora del corte automático.

Regla (Daniel, 2026-09-08): se cierra a las 18:00 todos los días, salvo
jueves y domingo que se cierra a las 17:00. El corte se hace 30 minutos
antes de cerrar. Lo vendido después del corte cae en el siguiente periodo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

CIERRE_NORMAL = time(18, 0)
CIERRE_TEMPRANO = time(17, 0)
DIAS_CIERRE_TEMPRANO = (3, 6)  # jueves, domingo
MINUTOS_ANTES_DEL_CIERRE = 30
# El resumen de Telegram sale 15 min antes de cerrar (17:45; jue/dom 16:45).
MINUTOS_ANTES_RESUMEN = 15
# Ventana en la que la tarea programada acepta que "es la hora" (por si
# Windows la dispara con unos minutos de retraso).
TOLERANCIA_MIN = 20

AUTO_CODE = "AUTO"


def hora_cierre(dia: date) -> time:
    return CIERRE_TEMPRANO if dia.weekday() in DIAS_CIERRE_TEMPRANO else CIERRE_NORMAL


def hora_corte(dia: date) -> time:
    cierre = datetime.combine(dia, hora_cierre(dia))
    return (cierre - timedelta(minutes=MINUTOS_ANTES_DEL_CIERRE)).time()


def momento_corte(dia: date) -> datetime:
    return datetime.combine(dia, hora_corte(dia))


def hora_resumen(dia: date) -> time:
    cierre = datetime.combine(dia, hora_cierre(dia))
    return (cierre - timedelta(minutes=MINUTOS_ANTES_RESUMEN)).time()


def es_momento_de_resumen(ahora: datetime, tolerancia_min: int = TOLERANCIA_MIN) -> bool:
    """True si `ahora` cae en la ventana del resumen de hoy (cierre − 15 min)."""
    objetivo = datetime.combine(ahora.date(), hora_resumen(ahora.date()))
    return objetivo <= ahora.replace(tzinfo=None) <= objetivo + timedelta(minutes=tolerancia_min)


def horas_de_resumen_posibles() -> list[time]:
    return sorted({hora_resumen(date(2026, 9, 7) + timedelta(days=i)) for i in range(7)})


def es_momento_de_corte(ahora: datetime, tolerancia_min: int = TOLERANCIA_MIN) -> bool:
    """True si `ahora` cae en la ventana del corte de hoy (hora exacta o
    hasta `tolerancia_min` después)."""
    objetivo = momento_corte(ahora.date())
    return objetivo <= ahora.replace(tzinfo=None) <= objetivo + timedelta(minutes=tolerancia_min)


def horas_de_corte_posibles() -> list[time]:
    """Horas distintas a las que puede tocar el corte (para programar tareas)."""
    return sorted({hora_corte(date(2026, 9, 7) + timedelta(days=i)) for i in range(7)})


def texto_horario_corte() -> str:
    normal = hora_corte(date(2026, 9, 7)).strftime("%H:%M")      # lunes
    temprano = hora_corte(date(2026, 9, 10)).strftime("%H:%M")   # jueves
    return f"El corte se hace solo a las {normal} (jueves y domingo a las {temprano})."


@dataclass(frozen=True)
class DecisionCorte:
    hacer: bool
    motivo: str


def decidir_corte_automatico(ahora: datetime, ultimo_corte: datetime | None, hay_movimiento: bool) -> DecisionCorte:
    """Lógica pura de la tarea programada: corre a cada hora posible y decide."""
    if not es_momento_de_corte(ahora):
        return DecisionCorte(False, f"no es la hora del corte de hoy ({hora_corte(ahora.date()):%H:%M})")
    if ultimo_corte is not None:
        u = ultimo_corte.astimezone().replace(tzinfo=None) if ultimo_corte.tzinfo else ultimo_corte
        if u.date() == ahora.date() and u >= momento_corte(ahora.date()) - timedelta(hours=1):
            return DecisionCorte(False, f"ya hubo corte hoy a las {u:%H:%M}")
    if not hay_movimiento:
        return DecisionCorte(False, "sin ventas ni pagos desde el último corte")
    return DecisionCorte(True, "toca el corte")
