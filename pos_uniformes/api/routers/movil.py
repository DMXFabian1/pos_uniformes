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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pos_uniformes.api.dependencies import get_current_employee, get_db

router = APIRouter(prefix="/api/v1/movil", tags=["movil"])

_OWNER_CODE = "VEND-1"
_ENCARGADO_CODE = "ENC-1"


def _modo_servidor() -> str:
    """"tienda" = PC principal con la base viva (puede encolar impresiones);
    "casa" = snapshot SQLite de solo lectura (consulta 24/7)."""
    from pos_uniformes.database.connection import engine

    return "casa" if engine.url.get_backend_name() == "sqlite" else "tienda"


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
        "modo": _modo_servidor(),
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


class EtiquetaRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=60)
    copies: int = Field(default=1, ge=1, le=20)


@router.post("/etiqueta")
def imprimir_etiqueta(
    body: EtiquetaRequest,
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    """Encola la etiqueta del SKU para que la imprima la Brother de la
    tienda (vía la cola `trabajo` que ya procesa el despachador del
    satélite). Solo disponible en modo tienda: el servidor de la casa lee
    un snapshot y no puede encolar nada."""
    if _modo_servidor() != "tienda":
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "solo_en_tienda",
                    "message": "Imprimir etiquetas solo funciona conectado a la tienda.",
                }
            },
        )
    empleada, _payload = current

    from pathlib import Path

    from sqlalchemy import func as sa_func, select

    from pos_uniformes.database.models import Variante
    from pos_uniformes.services import trabajos_service
    from pos_uniformes.services.inventory_label_service import render_inventory_label

    sku = body.sku.strip().upper()
    variante = db.scalar(
        select(Variante).where(
            sa_func.upper(Variante.sku) == sku, Variante.activo.is_(True)
        )
    )
    if variante is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "sku_no_encontrado",
                    "message": f"No se encontró producto con SKU '{sku}'.",
                }
            },
        )

    resultado = render_inventory_label(
        db, variante.id, mode="standard", requested_copies=body.copies
    )
    imagen = Path(resultado.image_path).read_bytes()
    trabajo = trabajos_service.enviar_etiqueta(
        db,
        imagen,
        sku=sku,
        copies=resultado.effective_copies,
        paper_mode=resultado.mode,
        origen="pwa",
        creado_por=str(empleada.codigo).upper(),
    )
    db.commit()
    return {
        "encolada": True,
        "trabajo_id": trabajo.id,
        "copias": resultado.effective_copies,
    }


# ─── Encargado (León) desde el celular — espejo de su modo del kiosko ────
# Lectura siempre; las ACCIONES (apuntar, hacer corte) solo en modo tienda
# (base viva). El ticket del corte se encola a la impresora del satélite.


def _es_gestor(codigo: str) -> bool:
    return _rol(codigo) in ("dueno", "encargado")


def _solo_gestor(empleada) -> None:
    if not _es_gestor(empleada.codigo):
        raise HTTPException(status_code=403, detail={"error": {
            "code": "solo_gestor", "message": "Solo el dueño o el encargado."}})


def _solo_tienda() -> None:
    if _modo_servidor() != "tienda":
        raise HTTPException(status_code=409, detail={"error": {
            "code": "solo_en_tienda",
            "message": "Esta acción solo funciona conectado a la tienda."}})


def _equipo(db: Session) -> list[dict]:
    from pos_uniformes.database.models import Empleada

    return [
        {"codigo": str(e.codigo).upper(),
         "nombre": (e.nombre_completo or e.codigo).split()[0]}
        for e in db.query(Empleada).filter(Empleada.activo.is_(True))
        .order_by(Empleada.nombre_completo).all()
        if str(e.codigo).upper() not in (_OWNER_CODE, _ENCARGADO_CODE)
    ]


def _descansos_semana(db: Session) -> list[dict]:
    """Quién descansa en los próximos 7 días (hoy incluido)."""
    from datetime import timedelta

    from pos_uniformes.services.calendario_empleadas_service import (
        cargar_horarios_todos,
        quienes_descansan,
    )

    horarios = cargar_horarios_todos(db)
    nombres = {e["codigo"]: e["nombre"] for e in _equipo(db)}
    hoy = date.today()
    filas = []
    for i in range(7):
        dia = hoy + timedelta(days=i)
        codes = [c for c in quienes_descansan(horarios, dia) if c in nombres]
        if codes:
            filas.append({
                "fecha": dia.isoformat(),
                "nombres": [nombres[c] for c in codes],
            })
    return filas


@router.get("/encargado")
def encargado_inicio(
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    empleada, _p = current
    _solo_gestor(empleada)
    return {
        "modo": _modo_servidor(),
        "cortes": _payload_cortes(db),
        "equipo": _equipo(db),
        "descansos_semana": _descansos_semana(db),
    }


class MarcarRequest(BaseModel):
    employee_code: str = Field(min_length=1, max_length=40)
    fecha: date
    tipo: str = Field(pattern="^(falta|descanso|quitar)$")


@router.post("/encargado/marcar")
def encargado_marcar(
    body: MarcarRequest,
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    empleada, _p = current
    _solo_gestor(empleada)
    _solo_tienda()
    from pos_uniformes.services.calendario_empleadas_service import (
        marcar_dia,
        quitar_marca,
    )

    quien = str(empleada.codigo).upper()
    if body.tipo == "quitar":
        quitar_marca(db, body.employee_code, body.fecha)
    else:
        marcar_dia(
            db, body.employee_code, body.fecha, body.tipo,
            nota=f"apuntado por {quien} (celular)",
        )
    db.commit()
    return {"ok": True}


@router.get("/encargado/corte_hoy")
def encargado_corte_hoy(
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    """La cifra calculada de hoy (para confirmarla — SIN poder editarla)."""
    from decimal import Decimal

    from pos_uniformes.services.libreta_service import (
        listar_operaciones,
        resumir_por_dia,
        ventana_hoy,
    )

    empleada, _p = current
    _solo_gestor(empleada)
    desde, hasta = ventana_hoy()
    cortes = resumir_por_dia(listar_operaciones(db, desde=desde, hasta=hasta))
    return {
        "venta": str(sum((c.monto_en_caja for c in cortes), Decimal("0.00"))),
        "operaciones": sum(c.operaciones for c in cortes),
        "piezas": sum(c.piezas for c in cortes),
        "hay_ventas": bool(cortes),
    }


@router.post("/encargado/corte")
def encargado_hacer_corte(
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    """Guarda el corte de hoy con la cifra CALCULADA (el encargado no puede
    editarla) y encola el ticket a la impresora de la tienda."""
    from decimal import Decimal

    from pos_uniformes.services import trabajos_service
    from pos_uniformes.services.libreta_service import (
        guardar_corte,
        listar_operaciones,
        resumir_por_dia,
        resumir_por_empleada,
        ventana_hoy,
    )
    from pos_uniformes.ui.helpers.libreta_corte_ticket_helper import (
        build_corte_ticket_text,
    )

    empleada, _p = current
    _solo_gestor(empleada)
    _solo_tienda()
    desde, hasta = ventana_hoy()
    rows = listar_operaciones(db, desde=desde, hasta=hasta)
    cortes = resumir_por_dia(rows)
    if not cortes:
        raise HTTPException(status_code=409, detail={"error": {
            "code": "sin_ventas", "message": "Hoy todavía no hay ventas."}})
    monto = sum((c.monto_en_caja for c in cortes), Decimal("0.00"))
    quien = str(empleada.codigo).upper()
    guardar_corte(
        db,
        fecha=date.today(),
        monto_final=monto,
        operaciones=sum(c.operaciones for c in cortes),
        piezas=sum(c.piezas for c in cortes),
        periodo_label="HOY",
        creado_por=quien,
    )
    ticket_encolado = False
    try:
        texto = build_corte_ticket_text(
            periodo_label="HOY", cortes=cortes,
            por_empleada=resumir_por_empleada(rows), generado_por=quien,
        )
        trabajos_service.enviar_ticket(db, texto, origen="pwa", creado_por=quien)
        ticket_encolado = True
    except Exception:  # noqa: BLE001 — el corte ya quedó; el ticket es extra
        pass
    db.commit()
    return {"ok": True, "monto": str(monto), "ticket_encolado": ticket_encolado}
