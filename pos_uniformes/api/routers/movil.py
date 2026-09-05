"""Endpoints de la PWA móvil — Fase 1, SOLO lectura.

Un endpoint principal (/inicio) devuelve el payload según el rol:
- empleada: su banner (comisiones desde el último pago, siguiente
  descanso, próximo pago) + su calendario del mes.
- encargado (ENC-1): la lista de cortes — solo fecha y cifra.
- dueño (VEND-1): venta de hoy, ranking de empleadas y el ciclo de cada
  una (comisiones desde su último pago), más los cortes.

/calendario permite navegar meses (empleada: el suyo).
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from pos_uniformes.api.dependencies import get_current_employee, get_db

router = APIRouter(prefix="/api/v1/movil", tags=["movil"])

_OWNER_CODE = "VEND-1"
_ENCARGADO_CODE = "ENC-1"


def _rol(codigo: str) -> str:
    code = str(codigo).strip().upper()
    if code == _OWNER_CODE:
        return "dueno"
    if code == _ENCARGADO_CODE:
        return "encargado"
    return "empleada"


def _payload_empleada(db: Session, codigo: str) -> dict:
    from pos_uniformes.services.calendario_empleadas_service import (
        cargar_horario,
        comisiones_desde_ultimo_pago,
        dias_para_pago,
        fecha_proximo_pago,
        proximo_descanso,
        resumen_empleada,
    )

    hoy = date.today()
    horario = cargar_horario(db, codigo)
    descanso = proximo_descanso(horario, hoy)
    proximo = fecha_proximo_pago(horario, hoy)
    return {
        "comisiones_ciclo": comisiones_desde_ultimo_pago(db, codigo, horario),
        "siguiente_descanso": descanso.isoformat() if descanso else None,
        "proximo_pago": proximo.isoformat() if proximo else None,
        "dias_para_pago": dias_para_pago(horario, hoy),
        "resumen": resumen_empleada(horario, hoy),
        "calendario": _calendario_mes(db, codigo, hoy.year, hoy.month),
    }


def _calendario_mes(db: Session, codigo: str, year: int, month: int) -> dict:
    from pos_uniformes.services.calendario_empleadas_service import (
        cargar_horario,
        pintar_mes,
    )

    horario = cargar_horario(db, codigo)
    return {
        "year": year,
        "month": month,
        "dias": {
            fecha.isoformat(): estado
            for fecha, estado in pintar_mes(horario, year, month).items()
        },
    }


def _payload_cortes(db: Session) -> list[dict]:
    from pos_uniformes.services.libreta_service import listar_cortes

    return [
        {
            "fecha": corte.fecha.isoformat(),
            "monto": str(corte.monto_final),
            "por": corte.creado_por,
        }
        for corte in listar_cortes(db, limit=15)
    ]


def _payload_dueno(db: Session) -> dict:
    from decimal import Decimal

    from pos_uniformes.database.models import Empleada, EmpleadaHorario
    from pos_uniformes.services.calendario_empleadas_service import (
        cargar_horario,
        comisiones_desde_ultimo_pago,
        fecha_proximo_pago,
    )
    from pos_uniformes.services.libreta_service import (
        listar_operaciones,
        resumir_por_dia,
        resumir_por_empleada,
        ventana_hoy,
    )

    hoy = date.today()
    desde, hasta = ventana_hoy()
    rows = listar_operaciones(db, desde=desde, hasta=hasta)
    cortes_hoy = resumir_por_dia(rows)
    nombres = {
        str(e.codigo).upper(): (e.nombre_completo or e.codigo)
        for e in db.query(Empleada).filter(Empleada.activo.is_(True)).all()
    }

    ciclos = []
    for fila in db.query(EmpleadaHorario).all():
        code = fila.employee_code
        if code in (_OWNER_CODE, _ENCARGADO_CODE):
            continue
        horario = cargar_horario(db, code)
        proximo = fecha_proximo_pago(horario, hoy)
        ciclos.append(
            {
                "codigo": code,
                "nombre": nombres.get(code, code),
                "comisiones_ciclo": comisiones_desde_ultimo_pago(db, code, horario),
                "proximo_pago": proximo.isoformat() if proximo else None,
            }
        )
    ciclos.sort(key=lambda c: c["nombre"])

    return {
        "hoy": {
            "venta": str(
                sum((c.monto_en_caja for c in cortes_hoy), Decimal("0.00"))
            ),
            "operaciones": sum(c.operaciones for c in cortes_hoy),
            "piezas": sum(c.piezas for c in cortes_hoy),
        },
        "ranking": [
            {
                "codigo": r.employee_code,
                "nombre": r.employee_name or r.employee_code,
                "comisiones": r.comisiones,
                "piezas": r.piezas,
                "operaciones": r.operaciones,
                "monto": str(r.monto_total),
            }
            for r in resumir_por_empleada(rows)
        ],
        "ciclos": ciclos,
        "cortes": _payload_cortes(db),
    }


@router.get("/inicio")
def inicio(
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    empleada, _payload = current
    rol = _rol(empleada.codigo)
    base = {
        "rol": rol,
        "codigo": str(empleada.codigo).upper(),
        "nombre": (empleada.nombre_completo or empleada.codigo).split()[0],
    }
    if rol == "dueno":
        base["dueno"] = _payload_dueno(db)
    elif rol == "encargado":
        base["cortes"] = _payload_cortes(db)
    else:
        base["empleada"] = _payload_empleada(db, str(empleada.codigo))
    return base


@router.get("/calendario")
def calendario(
    year: int,
    month: int,
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    """Mes navegable del calendario propio (Fase 1: cada quien el suyo)."""
    empleada, _payload = current
    year = max(2020, min(year, 2100))
    month = max(1, min(month, 12))
    return _calendario_mes(db, str(empleada.codigo), year, month)
