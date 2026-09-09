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
from decimal import Decimal

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

    from pos_uniformes.services.libreta_presentacion_service import tiles_ciclo

    hoy = date.today()
    horario = cargar_horario(db, codigo)
    descanso = proximo_descanso(horario, hoy)
    proximo = fecha_proximo_pago(horario, hoy)
    comisiones = comisiones_desde_ultimo_pago(db, codigo, horario)
    # La misma tarjeta del ciclo que ve en el kiosko (mismo texto).
    tiles = tiles_ciclo({
        "comisiones": comisiones,
        "proximo_pago": proximo,
        "faltan": dias_para_pago(horario, hoy),
        "descanso": descanso,
        "hoy": hoy,
    })
    return {
        "comisiones_ciclo": comisiones,
        "siguiente_descanso": descanso.isoformat() if descanso else None,
        "proximo_pago": proximo.isoformat() if proximo else None,
        "dias_para_pago": dias_para_pago(horario, hoy),
        "resumen": resumen_empleada(horario, hoy),
        "tiles": [{"valor": v, "leyenda": leyenda} for v, leyenda in tiles],
        "movimientos": _movimientos_empleada(db, codigo, horario),
        "calendario": _calendario_mes(db, codigo, hoy.year, hoy.month),
    }


def _movimientos_empleada(db: Session, codigo: str, horario) -> list[dict]:
    """Sus movimientos del ciclo, en el mismo lenguaje del kiosko y SIN
    dinero (regla de privacidad de la Libreta)."""
    from datetime import datetime, time, timedelta

    from pos_uniformes.services.libreta_presentacion_service import texto_movimiento
    from pos_uniformes.services.libreta_service import listar_operaciones

    ahora = datetime.now().astimezone()
    hoy_cero = datetime.combine(date.today(), time.min).astimezone()
    desde = hoy_cero
    if getattr(horario, "fecha_ultimo_pago", None) is not None:
        # Desde su último pago, pero lo de HOY siempre se ve (si le pagaron
        # hoy, el ciclo nuevo empieza mañana y se quedaría sin nada).
        desde = min(
            datetime.combine(horario.fecha_ultimo_pago + timedelta(days=1), time.min).astimezone(),
            hoy_cero,
        )
    rows = listar_operaciones(db, desde=desde, hasta=ahora, employee_code=codigo)
    return [
        {"texto": texto_movimiento(row, con_dia=True), "tipo": str(row.tipo)}
        for row in rows[:50]
    ]


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
    """Los cortes como los muestra el satélite: el periodo que cubren, lo que
    se retiró y el fondo que quedó. `monto` es siempre la cifra OFICIAL (la
    del dueño); el real que solo ve Daniel no sale al celular."""
    from pos_uniformes.services.historial_cortes_service import es_legacy, retirado
    from pos_uniformes.services.libreta_service import listar_cortes

    filas = []
    for corte in listar_cortes(db, limit=15):
        legacy = es_legacy(corte)
        filas.append({
            "fecha": corte.fecha.isoformat(),
            "monto": str(corte.monto_final),
            "por": corte.creado_por,
            "periodo": corte.periodo_label or "HOY",
            "legacy": legacy,
            # En los viejos (totales del día) no hubo retiro ni fondo: '—'.
            "retirado": None if legacy else str(retirado(corte)),
            "reactivo_final": None if legacy else str(corte.reactivo_final),
        })
    return filas


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

    # Principio de Daniel (2026-09-06): la Libreta solo habla de dinero REAL
    # — nada de "vendido en total" (el valor de un apartado no es dinero
    # recibido). Mismas cuatro cifras que la vista del dueño en el satélite.
    en_caja = sum((c.monto_en_caja for c in cortes_hoy), Decimal("0.00"))
    neto = sum((c.monto_neto_ventas for c in cortes_hoy), Decimal("0.00"))
    abonos = sum((c.monto_abonos for c in cortes_hoy), Decimal("0.00"))
    ventas = sum((c.monto_ventas for c in cortes_hoy), Decimal("0.00"))
    tarjeta = sum(
        (
            Decimal(str(r.monto_total or 0))
            for r in rows
            if str(r.tipo) == "venta" and bool(getattr(r, "pago_tarjeta", False))
        ),
        Decimal("0.00"),
    )
    comisiones = sum(int(getattr(r, "comisiones", 0) or 0) for r in rows)
    ventas_count = sum(1 for r in rows if str(r.tipo) == "venta")

    return {
        "hoy": {
            "en_caja": str(en_caja),
            "tarjeta": str(tarjeta),
            "neto_tarjeta": str(neto - (ventas - tarjeta)),
            "abonos": str(abonos),
            "comisiones": comisiones,
            "ventas": ventas_count,
            "operaciones": sum(c.operaciones for c in cortes_hoy),
            "piezas": sum(c.piezas for c in cortes_hoy),
            # Compatibilidad con la PWA anterior (era la cifra del cajón).
            "venta": str(en_caja),
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
        "resumen": _resumen_encargado(db),
        "tarjetas": _tarjetas_encargado(db),
        "pagos": _payload_pagos(db),
    }


def _tarjetas_encargado(db: Session) -> dict:
    """Lo mismo que el menú del kiosko de León (rediseño 2026-09-09): quién
    descansa hoy y mañana con nombre de pila, y los pagos en una línea por
    persona con la fecha ya en español (`cuando_pago`)."""
    try:
        from pos_uniformes.services.nomina_service import (
            cuando_pago,
            resumen_para_encargado,
        )

        resumen = resumen_para_encargado(db)
    except Exception:  # noqa: BLE001 — base sin migrar o snapshot viejo
        return {"descansan_hoy": [], "descansan_manana": [], "pagos": []}

    def _pila(nombre: str) -> str:
        return (nombre or "").split()[0] if nombre else ""

    pagos = []
    for a in resumen.pagos:
        cuando = cuando_pago(a)
        pagos.append({
            "nombre": _pila(a.employee_name),
            "cuando": cuando,
            "total": str(a.total_estimado),
            "urgente": cuando == "HOY" or cuando.startswith("ATRASADO"),
        })
    return {
        "descansan_hoy": [_pila(n) for n in resumen.descansan_hoy],
        "descansan_manana": [_pila(n) for n in resumen.descansan_manana],
        "pagos": pagos,
    }


def _resumen_encargado(db: Session) -> str:
    """Quién descansa hoy/mañana y pagos de la semana (texto llano)."""
    try:
        from pos_uniformes.services.nomina_service import (
            resumen_para_encargado,
            texto_resumen_encargado,
        )

        return texto_resumen_encargado(resumen_para_encargado(db))
    except Exception:  # noqa: BLE001 — base sin migrar o snapshot viejo
        return ""


def _payload_pagos(db: Session) -> list[dict]:
    try:
        from pos_uniformes.services.nomina_service import avisos_de_pago

        avisos = avisos_de_pago(db, dias=365)
    except Exception:  # noqa: BLE001
        return []
    return [
        {
            "codigo": a.employee_code,
            "nombre": a.employee_name,
            "fecha_pago": a.fecha_pago.isoformat() if a.fecha_pago else None,
            "dias": a.dias_para_pago,
            "comisiones": a.comisiones,
            "total": str(a.total_estimado),
        }
        for a in avisos
    ]


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
    """Estado de la caja del periodo (desde el corte anterior): lo que debe
    haber en el cajón. El encargado captura lo contado en /encargado/corte."""
    from pos_uniformes.services.corte_caja_service import estado_caja

    from pos_uniformes.services.corte_caja_service import pagos_que_tocan_hoy

    empleada, _p = current
    _solo_gestor(empleada)
    estado = estado_caja(db)
    r = estado.resumen
    avisos = pagos_que_tocan_hoy(db)
    total_pagos = sum((a.total_estimado for a in avisos), Decimal("0"))
    return {
        "pagos_hoy": [
            {"codigo": a.employee_code, "nombre": a.employee_name, "total": str(a.total_estimado), "comisiones": a.comisiones}
            for a in avisos
        ],
        "retiro": str((r.efectivo - estado.pagos - total_pagos - estado.total_retiros).quantize(Decimal("0.01"))),
        "retiros_apuntados": str(estado.total_retiros),
        "desde": estado.desde.isoformat() if estado.desde else None,
        "hasta": estado.hasta.isoformat(),
        "reactivo": str(estado.reactivo),
        "efectivo": str(r.efectivo),
        "tarjeta": str(r.tarjeta),
        "pagos": str(estado.pagos),
        "esperado": str(estado.esperado),
        "operaciones": r.operaciones,
        "piezas": r.piezas,
        "hay_ventas": r.operaciones > 0,
        # Compatibilidad con la PWA anterior.
        "venta": str(r.efectivo),
    }


@router.post("/encargado/corte")
def encargado_hacer_corte(
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    """Corte de un botón: registra los pagos que tocan hoy, cierra con la
    cifra calculada (el encargado no cuenta ni captura) y encola el ticket."""
    from pos_uniformes.services import trabajos_service
    from pos_uniformes.services.corte_caja_service import cerrar_corte_automatico, operaciones_del_periodo
    from pos_uniformes.services.libreta_service import resumir_por_empleada
    from pos_uniformes.ui.dialogs.corte_caja_dialog import texto_ticket_corte_encargado

    empleada, _p = current
    _solo_gestor(empleada)
    _solo_tienda()
    quien = str(empleada.codigo).upper()
    auto = cerrar_corte_automatico(db, creado_por=quien)
    rows = operaciones_del_periodo(db, auto.estado.desde, auto.estado.hasta)
    ticket_encolado = False
    try:
        from pos_uniformes.services.retiros_service import retiros_del_periodo

        try:
            retiros = retiros_del_periodo(db, auto.estado.desde, auto.estado.hasta)
        except Exception:  # noqa: BLE001 — base sin la tabla todavía
            db.rollback()
            retiros = []
        texto = texto_ticket_corte_encargado(
            auto.corte, auto.estado.resumen.efectivo, auto.pagos, resumir_por_empleada(rows), retiros=retiros
        )
        trabajos_service.enviar_ticket(db, texto, origen="pwa", creado_por=quien)
        ticket_encolado = True
        db.commit()
    except Exception:  # noqa: BLE001 — el corte ya quedó; el ticket es extra
        pass
    retiro = (Decimal(auto.corte.monto_final) - Decimal(auto.corte.reactivo_final)).quantize(Decimal("0.01"))
    return {
        "ok": True,
        "monto": str(auto.corte.monto_final),
        "venta": str(auto.estado.resumen.efectivo),
        "retiro": str(retiro),
        "reactivo_final": str(auto.corte.reactivo_final),
        "pagos": [{"nombre": p.employee_name, "total": str(p.total)} for p in auto.pagos],
        "ticket_encolado": ticket_encolado,
    }


class PagarRequest(BaseModel):
    employee_code: str = Field(min_length=1, max_length=40)


@router.get("/encargado/pago_pendiente/{employee_code}")
def encargado_pago_pendiente(
    employee_code: str,
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    """Desglose de lo que se le pagaría hoy a la empleada (sin registrar)."""
    from pos_uniformes.services.nomina_service import pago_pendiente

    empleada, _p = current
    _solo_gestor(empleada)
    d = pago_pendiente(db, employee_code)
    return {
        "codigo": d.employee_code,
        "desde": d.desde.isoformat() if d.desde else None,
        "hasta": d.hasta.isoformat(),
        "comisiones": d.comisiones,
        "sueldo_base": str(d.sueldo_base),
        "tarifa_comision": str(d.tarifa_comision),
        "monto_comisiones": str(d.monto_comisiones),
        "faltas": d.faltas,
        "descuento_faltas": str(d.descuento_faltas),
        "total": str(d.total),
    }


@router.post("/encargado/pagar")
def encargado_pagar(
    body: PagarRequest,
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    """Registra el pago con su desglose; el corte lo descuenta del cajón."""
    from pos_uniformes.services.nomina_service import registrar_pago_con_monto

    empleada, _p = current
    _solo_gestor(empleada)
    _solo_tienda()
    quien = str(empleada.codigo).upper()
    try:
        pago = registrar_pago_con_monto(db, body.employee_code, creado_por=quien)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"error": {"code": "sin_permiso", "message": str(exc)}})
    return {"ok": True, "total": str(pago.total), "comisiones": pago.comisiones, "faltas": pago.faltas}


class RetiroRequest(BaseModel):
    monto: Decimal = Field(gt=0)
    motivo: str = Field(min_length=1, max_length=120)


@router.post("/encargado/retiro")
def encargado_retiro(
    body: RetiroRequest,
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    """Saqué dinero del cajón (proveedor, renta...). El corte lo descuenta."""
    from pos_uniformes.services.retiros_service import registrar_retiro

    empleada, _p = current
    _solo_gestor(empleada)
    _solo_tienda()
    try:
        retiro = registrar_retiro(db, monto=body.monto, motivo=body.motivo, creado_por=str(empleada.codigo).upper())
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=422, detail={"error": {"code": "retiro_invalido", "message": str(exc)}})
    return {"ok": True, "id": retiro.id, "monto": str(retiro.monto), "motivo": retiro.motivo}


# ─── Corte del dueño desde el celular ────────────────────────────────────
# Igual que "Hacer corte" del satélite: él cuenta el cajón y su cifra es la
# oficial (el real calculado se guarda aparte y no sale al celular).


def _solo_dueno(empleada) -> None:
    if _rol(empleada.codigo) != "dueno":
        raise HTTPException(status_code=403, detail={"error": {
            "code": "solo_dueno", "message": "Solo el dueño hace este corte."}})


@router.get("/dueno/corte_estado")
def dueno_corte_estado(
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    """Lo que debe haber en el cajón antes de contarlo."""
    from pos_uniformes.services.corte_caja_service import _etiqueta_periodo, estado_caja

    empleada, _p = current
    _solo_dueno(empleada)
    estado = estado_caja(db)
    r = estado.resumen
    return {
        "periodo": _etiqueta_periodo(estado.desde, estado.hasta),
        "desde": estado.desde.isoformat() if estado.desde else None,
        "hasta": estado.hasta.isoformat(),
        "reactivo": str(estado.reactivo),
        "efectivo": str(r.efectivo),
        "tarjeta": str(r.tarjeta),
        "pagos": str(estado.pagos),
        "retiros_apuntados": str(estado.total_retiros),
        "esperado": str(estado.esperado),
        "operaciones": r.operaciones,
        "piezas": r.piezas,
    }


class CorteDuenoRequest(BaseModel):
    contado: Decimal = Field(ge=0)
    reactivo_final: Decimal = Field(ge=0)
    otros_retiros: Decimal = Field(default=Decimal("0"), ge=0)
    nota: str = Field(default="", max_length=200)


@router.post("/dueno/corte")
def dueno_hacer_corte(
    body: CorteDuenoRequest,
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    from pos_uniformes.services import trabajos_service
    from pos_uniformes.services.corte_caja_service import (
        cerrar_corte,
        estado_caja,
        operaciones_del_periodo,
        pagos_registrados_del_periodo,
    )
    from pos_uniformes.services.libreta_service import resumir_por_empleada
    from pos_uniformes.ui.dialogs.corte_caja_dialog import texto_ticket_corte

    empleada, _p = current
    _solo_dueno(empleada)
    _solo_tienda()
    quien = str(empleada.codigo).upper()
    estado = estado_caja(db)
    por_empleada = resumir_por_empleada(
        operaciones_del_periodo(db, estado.desde, estado.hasta)
    )
    try:
        corte = cerrar_corte(
            db,
            contado=body.contado,
            reactivo_final=body.reactivo_final,
            otros_retiros=body.otros_retiros,
            nota=body.nota,
            creado_por=quien,
            ahora=estado.hasta,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": {
            "code": "corte_invalido", "message": str(exc)}})

    ticket_encolado = False
    try:
        try:
            from pos_uniformes.services.retiros_service import retiros_del_periodo

            retiros = retiros_del_periodo(db, estado.desde, estado.hasta)
        except Exception:  # noqa: BLE001 — base sin la tabla todavía
            db.rollback()
            retiros = []
        texto = texto_ticket_corte(
            corte,
            por_empleada,
            pagos=pagos_registrados_del_periodo(db, estado.desde, estado.hasta),
            venta_efectivo=estado.resumen.efectivo,
            retiros=retiros,
        )
        trabajos_service.enviar_ticket(db, texto, origen="pwa", creado_por=quien)
        ticket_encolado = True
        db.commit()
    except Exception:  # noqa: BLE001 — el corte ya quedó; el ticket es extra
        pass

    retiro = (Decimal(corte.monto_final) - Decimal(corte.reactivo_final)).quantize(Decimal("0.01"))
    return {
        "ok": True,
        "periodo": corte.periodo_label,
        "monto": str(corte.monto_final),
        "retiro": str(retiro),
        "reactivo_final": str(corte.reactivo_final),
        "ticket_encolado": ticket_encolado,
    }
