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
from pos_uniformes.services.nombres_empleadas_service import mostrar, nombres_por_codigo

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
    nombres = nombres_por_codigo(db)
    for corte in listar_cortes(db, limit=15):
        legacy = es_legacy(corte)
        filas.append({
            "fecha": corte.fecha.isoformat(),
            "monto": str(corte.monto_final),
            "por": mostrar(corte.creado_por, nombres),
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
    # «Hoy» es desde el último corte, como en la Libreta del kiosko: lo vendido
    # después del corte de ayer es dinero que se entrega hoy (2026-10-15).
    from pos_uniformes.services.libreta_service import desde_el_corte, etiqueta_desde_el_corte, hora_local

    try:
        from pos_uniformes.services.corte_caja_service import inicio_periodo

        inicio_corte = hora_local(inicio_periodo(db))
    except Exception:  # noqa: BLE001 — sin el dato, el día de calendario
        db.rollback()
        inicio_corte = None
    consulta_desde = inicio_corte if inicio_corte is not None and inicio_corte < desde else desde
    rows = desde_el_corte(listar_operaciones(db, desde=consulta_desde, hasta=hasta), inicio_corte)
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
            "periodo": etiqueta_desde_el_corte(inicio_corte),
        },
        "ranking": [
            {
                "codigo": r.employee_code,
                "nombre": mostrar(r.employee_name or r.employee_code, nombres_por_codigo(db)),
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


# ─── Encargado (ENC-1) desde el celular — espejo de su modo del kiosko ────
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
    """Lo mismo que el menú del kiosko del encargado (rediseño 2026-09-09): quién
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
    tipo: str = Field(pattern="^(falta|descanso|trabajo|quitar)$")


@router.get("/encargado/marcas/{employee_code}")
def encargado_marcas(
    employee_code: str,
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    """Las marcas de las últimas dos semanas de una persona (falta / descanso
    / vino), para corregir desde el celular sin tener que ir al kiosko
    (Daniel 2026-09-19: "le puse que faltó Naye hoy y no tengo manera de
    corregirlo"). También su equipo, para elegir a otra sin regresar."""
    from datetime import timedelta

    from pos_uniformes.services.calendario_empleadas_service import DESCANSO, FALTA, TRABAJO, cargar_horario

    empleada, _p = current
    _solo_gestor(empleada)
    code = employee_code.strip().upper()
    horario = cargar_horario(db, code)
    hoy = date.today()
    desde = hoy - timedelta(days=14)
    etiqueta = {FALTA: "Faltó", DESCANSO: "Descansó", TRABAJO: "Sí vino", "vacaciones": "Vacaciones"}
    marcas = [
        {"fecha": f.isoformat(), "tipo": t, "texto": etiqueta.get(t, t)}
        for f, t in sorted(horario.eventos.items(), reverse=True)
        if desde <= f <= hoy + timedelta(days=7) and t in etiqueta
    ]
    nombre = next((e["nombre"] for e in _equipo(db) if e["codigo"] == code), code)
    return {"codigo": code, "nombre": nombre, "marcas": marcas}


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
        quitar_marca(db, body.employee_code, body.fecha, actor=quien, origen="movil")
    else:
        marcar_dia(
            db, body.employee_code, body.fecha, body.tipo,
            nota=f"apuntado por {quien} (celular)", actor=quien, origen="movil",
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
    from pos_uniformes.services.corte_caja_service import (
        datos_ticket_encargado,
        estado_caja,
        pagos_que_tocan_hoy,
    )

    empleada, _p = current
    _solo_gestor(empleada)
    quien = str(empleada.codigo).upper()
    estado = estado_caja(db)
    r = estado.resumen
    avisos = pagos_que_tocan_hoy(db)
    total_pagos = sum((a.total_estimado for a in avisos), Decimal("0"))
    # El DINERO de los cobros privados del dueño no existe para el encargado
    # (las piezas y las comisiones sí: la empleada cobra lo que trabajó).
    from pos_uniformes.services.nomina_service import ve_privados

    tarjeta = r.tarjeta
    if not ve_privados(quien):
        tarjeta = datos_ticket_encargado(db, estado.desde, estado.hasta).tarjeta
    return {
        "pagos_hoy": [
            {"codigo": a.employee_code, "nombre": a.employee_name, "total": str(a.total_estimado), "comisiones": a.comisiones}
            for a in avisos
        ],
        "retiro": str((r.efectivo + estado.entradas - estado.pagos - total_pagos - estado.total_retiros).quantize(Decimal("0.01"))),
        "retiros_apuntados": str(estado.total_retiros),
        "entradas": str(estado.entradas),
        "desde": estado.desde.isoformat() if estado.desde else None,
        "hasta": estado.hasta.isoformat(),
        "reactivo": str(estado.reactivo),
        "efectivo": str(r.efectivo),
        "tarjeta": str(tarjeta),
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
    from pos_uniformes.services.corte_caja_service import (
        cerrar_corte_automatico,
        datos_ticket_encargado,
    )
    from pos_uniformes.ui.dialogs.corte_caja_dialog import texto_ticket_corte_encargado

    empleada, _p = current
    _solo_gestor(empleada)
    _solo_tienda()
    quien = str(empleada.codigo).upper()
    auto = cerrar_corte_automatico(db, creado_por=quien)
    ticket_encolado = False
    try:
        # Ese papel se queda en la tienda: sin los movimientos privados.
        datos = datos_ticket_encargado(db, auto.estado.desde, auto.estado.hasta)
        texto = texto_ticket_corte_encargado(
            auto.corte, auto.estado.resumen.efectivo, auto.pagos, datos.por_empleada,
            retiros=datos.retiros, tarjeta=datos.tarjeta, tarjeta_ops=datos.tarjeta_ops,
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
        "prestamo": str(getattr(d, "prestamo_cubierto", Decimal("0.00"))),
        "prestamo_sin_cubrir": str(getattr(d, "prestamo_sin_cubrir", Decimal("0.00"))),
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
    """Lo que debe haber en el cajón antes de contarlo, con el mismo detalle
    que la ventana del corte en la PC (Daniel, 2026-10-26: «algo así como lo
    hago ahora desde PC»): cada pago y retiro del periodo con su casilla de
    «salió del cajón», lo que entró sin ser venta, y los pagos que tocan hoy."""
    from pos_uniformes.services.corte_caja_service import (
        _etiqueta_periodo, cargar_parametros, estado_caja, pagos_que_tocan_hoy, pagos_registrados_del_periodo,
    )

    empleada, _p = current
    _solo_dueno(empleada)
    estado = estado_caja(db)
    r = estado.resumen
    nombres = nombres_por_codigo(db)

    def _cuando(m) -> str:
        try:
            return (m.astimezone() if m.tzinfo else m).strftime("%d/%m %H:%M")
        except Exception:  # noqa: BLE001
            return ""

    pagos_hechos = [
        {"id": p.id, "quien": str(mostrar(p.employee_name or p.employee_code, nombres)).split()[0],
         "monto": str(Decimal(p.total)), "cuando": _cuando(p.created_at), "en_cajon": bool(p.en_cajon)}
        for p in pagos_registrados_del_periodo(db, estado.desde, estado.hasta, solo_en_cajon=False)
    ]
    try:
        from pos_uniformes.services.retiros_service import retiros_del_periodo

        retiros_hechos = [
            {"id": x.id, "motivo": str(x.motivo or "Retiro"), "monto": str(Decimal(x.monto)),
             "cuando": _cuando(x.created_at), "en_cajon": bool(x.en_cajon)}
            for x in retiros_del_periodo(db, estado.desde, estado.hasta, solo_en_cajon=False)
        ]
    except Exception:  # noqa: BLE001 — base sin la tabla todavía
        db.rollback()
        retiros_hechos = []
    try:
        from pos_uniformes.services.entradas_service import entradas_del_periodo

        entradas_hechas = [
            {"motivo": str(x.motivo or "Entrada"), "monto": str(Decimal(x.monto)), "cuando": _cuando(x.created_at)}
            for x in entradas_del_periodo(db, estado.desde, estado.hasta)
        ]
    except Exception:  # noqa: BLE001
        db.rollback()
        entradas_hechas = []
    try:
        pagos_hoy = [
            {"codigo": a.employee_code, "nombre": str(mostrar(a.employee_name or a.employee_code, nombres)).split()[0],
             "total": str(Decimal(a.total_estimado)), "comisiones": int(a.comisiones), "prestamos": str(Decimal(a.prestamos or 0))}
            for a in pagos_que_tocan_hoy(db, estado.hasta.date())
        ]
    except Exception:  # noqa: BLE001
        db.rollback()
        pagos_hoy = []
    return {
        # Cómo dejó el dueño la casilla la última vez (kiosko o celular).
        "ocultar_tarjeta": bool(getattr(cargar_parametros(db), "ocultar_tarjeta", False)),
        "periodo": _etiqueta_periodo(estado.desde, estado.hasta),
        "desde": estado.desde.isoformat() if estado.desde else None,
        "hasta": estado.hasta.isoformat(),
        "reactivo": str(estado.reactivo),
        "efectivo": str(r.efectivo),
        "tarjeta": str(r.tarjeta),
        "tarjeta_neto": str(r.tarjeta_neto),
        "pagos": str(estado.pagos),
        "retiros_apuntados": str(estado.total_retiros),
        "entradas": str(estado.entradas),
        "esperado": str(estado.esperado),
        "operaciones": r.operaciones,
        "piezas": r.piezas,
        "pagos_hechos": pagos_hechos,
        "retiros_hechos": retiros_hechos,
        "entradas_hechas": entradas_hechas,
        "pagos_hoy": pagos_hoy,
    }


class CorteDuenoRequest(BaseModel):
    # Camino viejo: él cuenta el cajón y manda la cifra.
    contado: Decimal | None = Field(default=None, ge=0)
    # Camino de la PC (2026-10-26): se razona con la VENTA y el cajón se calcula.
    venta: Decimal | None = Field(default=None, ge=0)
    reactivo_final: Decimal = Field(ge=0)
    otros_retiros: Decimal = Field(default=Decimal("0"), ge=0)
    entro: Decimal = Field(default=Decimal("0"), ge=0)          # entró sin ser venta (fondo de papá)
    entro_motivo: str = Field(default="", max_length=120)
    nota: str = Field(default="", max_length=200)
    # Solo el papel: la línea "Con tarjeta" no sale en este ticket.
    ocultar_tarjeta: bool = False
    # Casillas de lo que ya salió: desmarcado = NO salió del cajón en este periodo.
    fuera_pagos: list[int] = Field(default_factory=list)
    fuera_retiros: list[int] = Field(default_factory=list)
    dentro_pagos: list[int] = Field(default_factory=list)
    dentro_retiros: list[int] = Field(default_factory=list)
    # Pagos que tocan hoy y se pagan del cajón en este corte (códigos).
    pagar_hoy: list[str] = Field(default_factory=list)


@router.post("/dueno/corte")
def dueno_hacer_corte(
    body: CorteDuenoRequest,
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    """El corte del dueño, en el mismo orden que `hacer_corte_caja` de la PC:
    pagos de hoy marcados → entrada → casillas de lo que salió → cerrar →
    ticket simple a la impresora de la tienda."""
    from pos_uniformes.services import trabajos_service
    from pos_uniformes.services.corte_caja_service import (
        cerrar_corte,
        estado_caja,
        marcar_fuera_del_cajon,
        operaciones_del_periodo,
        pagos_registrados_del_periodo,
    )
    from pos_uniformes.services.libreta_service import resumir_por_empleada
    from pos_uniformes.ui.dialogs.corte_caja_dialog import contar_tarjeta, texto_ticket_corte_encargado

    empleada, _p = current
    _solo_dueno(empleada)
    _solo_tienda()
    quien = str(empleada.codigo).upper()
    if body.contado is None and body.venta is None:
        raise HTTPException(status_code=422, detail={"error": {"code": "corte_invalido", "message": "Falta la venta."}})
    estado = estado_caja(db)
    rows_periodo = operaciones_del_periodo(db, estado.desde, estado.hasta)
    por_empleada = resumir_por_empleada(rows_periodo)
    try:
        if body.pagar_hoy:
            from pos_uniformes.services.nomina_service import registrar_pago_con_monto

            for code in body.pagar_hoy:
                registrar_pago_con_monto(
                    db, code, creado_por=quien, fecha=estado.hasta.date(), momento=estado.hasta,
                )
        if body.entro > 0:
            from pos_uniformes.services.entradas_service import registrar_entrada

            registrar_entrada(db, monto=body.entro, motivo=body.entro_motivo, creado_por=quien, momento=estado.hasta)
        marcar_fuera_del_cajon(db, pagos_ids=body.fuera_pagos, retiros_ids=body.fuera_retiros, en_cajon=False)
        marcar_fuera_del_cajon(db, pagos_ids=body.dentro_pagos, retiros_ids=body.dentro_retiros, en_cajon=True)
        if body.venta is not None:
            # Lo que debe quedar si la venta en efectivo fue esa: la misma cuenta
            # que la PC, con todo lo de arriba ya aplicado.
            despues = estado_caja(db, estado.hasta, otros_retiros=body.otros_retiros)
            contado = max(
                despues.reactivo + Decimal(body.venta) + despues.entradas - despues.pagos - despues.total_retiros,
                Decimal("0.00"),
            ).quantize(Decimal("0.01"))
            venta = Decimal(body.venta).quantize(Decimal("0.01"))
        else:
            contado = Decimal(body.contado)
            venta = estado.resumen.efectivo
        corte = cerrar_corte(
            db,
            contado=contado,
            reactivo_final=body.reactivo_final,
            otros_retiros=body.otros_retiros,
            nota=body.nota,
            creado_por=quien,
            ahora=estado.hasta,
        )
    except (ValueError, PermissionError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"error": {
            "code": "corte_invalido", "message": str(exc)}})

    from pos_uniformes.services.corte_caja_service import recordar_ocultar_tarjeta

    recordar_ocultar_tarjeta(db, body.ocultar_tarjeta)
    ocultos = 0
    if body.ocultar_tarjeta:
        # Privados: desaparecen de todo lo que ve el encargado, no solo de
        # este papel.
        from pos_uniformes.services.libreta_service import marcar_privadas_del_periodo

        ocultos = marcar_privadas_del_periodo(
            db, estado.desde, estado.hasta, creado_por=quien
        )

    ticket_encolado = False
    try:
        try:
            from pos_uniformes.services.retiros_service import retiros_del_periodo

            retiros = retiros_del_periodo(db, estado.desde, estado.hasta)
        except Exception:  # noqa: BLE001 — base sin la tabla todavía
            db.rollback()
            retiros = []
        try:
            from pos_uniformes.services.entradas_service import entradas_del_periodo

            entradas = entradas_del_periodo(db, estado.desde, estado.hasta)
        except Exception:  # noqa: BLE001
            db.rollback()
            entradas = []
        # El ticket SIMPLE, el mismo que imprime la PC (2026-09-10).
        texto = texto_ticket_corte_encargado(
            corte,
            venta,
            [],
            por_empleada,
            retiros=retiros,
            tarjeta=None if body.ocultar_tarjeta else estado.resumen.tarjeta,
            tarjeta_ops=None if body.ocultar_tarjeta else contar_tarjeta(rows_periodo),
            tarjeta_neto=None if body.ocultar_tarjeta else estado.resumen.tarjeta_neto,
            ya_pagados=pagos_registrados_del_periodo(db, estado.desde, estado.hasta),
            entradas=entradas,
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
        "venta": str(venta),
        "ticket_encolado": ticket_encolado,
        "ocultos": ocultos,
    }


# ── Por nombrar: ropa normal que entró con el código del proveedor ───────────
# Daniel la nombra con la prenda en la mano (2026-10-20). Mismo servicio que
# la pantalla del POS, para que el celular y el POS nunca difieran.

class NombrarRequest(BaseModel):
    producto_id: int
    nombre: str = Field(min_length=1, max_length=150)
    pieza: str = Field(default="", max_length=80)
    detalle: str = Field(default="", max_length=80)
    color: str = Field(default="", max_length=50)
    genero: str = Field(default="", max_length=50)
    listo: bool = True
    imprimir_etiquetas: bool = False


def _usuario_admin(db: Session):
    from pos_uniformes.database.models import RolUsuario, Usuario

    u = db.query(Usuario).filter(Usuario.rol == RolUsuario.ADMIN, Usuario.activo.is_(True)).order_by(Usuario.id).first()
    if u is None:
        raise HTTPException(status_code=409, detail={"error": {
            "code": "sin_admin", "message": "No hay un usuario ADMIN para firmar el cambio."}})
    return u


@router.get("/dueno/por_nombrar")
def dueno_por_nombrar(
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    from pos_uniformes.database.models import AtributoProducto, TipoPieza
    from pos_uniformes.services import por_nombrar_service as pn

    empleada, _p = current
    _solo_dueno(empleada)
    return {
        "pendientes": [p.__dict__ for p in pn.listar(db)],
        "piezas": [t.nombre for t in db.query(TipoPieza).order_by(TipoPieza.nombre).all()],
        "detalles": [a.nombre for a in db.query(AtributoProducto).order_by(AtributoProducto.nombre).all()],
    }


@router.post("/dueno/nombrar")
def dueno_nombrar(
    body: NombrarRequest,
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    from pos_uniformes.services import por_nombrar_service as pn

    empleada, _p = current
    _solo_dueno(empleada)
    _solo_tienda()
    try:
        producto = pn.nombrar(
            db, _usuario_admin(db), body.producto_id,
            nombre=body.nombre, pieza=body.pieza, detalle=body.detalle,
            color=body.color, genero=body.genero, listo=body.listo,
        )
    except pn.NoSePuede as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"error": {"code": "no_se_puede", "message": str(exc)}})
    db.commit()
    etiquetas = 0
    if body.imprimir_etiquetas:
        etiquetas = pn.encolar_etiquetas(
            db, pn.skus_de(db, [producto.id]), origen="pwa", creado_por=str(empleada.codigo),
        )
        db.commit()
    return {"ok": True, "nombre": producto.nombre, "quedan": pn.cuantos(db), "etiquetas": etiquetas}


# ── La foto del modelo, desde el celular ────────────────────────────────────
# Base64 dentro del JSON y no multipart: el servidor no trae python-multipart
# y una foto de celular ya recortada aquí no pasa de unos cientos de KB.

class FotoRequest(BaseModel):
    producto_id: int
    imagen_b64: str = Field(min_length=1)


@router.post("/dueno/producto_foto")
def dueno_producto_foto(
    body: FotoRequest,
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
) -> dict:
    import base64

    from pos_uniformes.services import producto_foto_service as fotos

    empleada, _p = current
    _solo_dueno(empleada)
    _solo_tienda()
    crudo = body.imagen_b64.split(",", 1)[-1]          # tolera «data:image/jpeg;base64,…»
    try:
        datos = base64.b64decode(crudo, validate=False)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=422, detail={"error": {"code": "imagen", "message": "La imagen no se pudo leer."}})
    try:
        foto = fotos.guardar(db, body.producto_id, datos)
    except fotos.NoSePuede as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"error": {"code": "imagen", "message": str(exc)}})
    db.commit()
    return {"ok": True, "hash": foto.hash, "ancho": foto.ancho, "alto": foto.alto}


@router.get("/producto/{producto_id}/foto")
def producto_foto(
    producto_id: int,
    tam: str = "mini",
    current: tuple = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """La foto del modelo (mini para listas, media para la ficha). 404 si no hay."""
    from fastapi import Response

    from pos_uniformes.services import producto_foto_service as fotos

    datos = fotos.mediana(db, producto_id) if tam == "media" else fotos.miniatura(db, producto_id)
    if not datos:
        raise HTTPException(status_code=404, detail={"error": {"code": "sin_foto", "message": "Ese modelo no tiene foto."}})
    return Response(content=datos, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})
